import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const EVENT_NAME = "text-processor-global-random-seed";
const EXTENSION_NAME = "ComfyUI.TextProcessor.GlobalRandomSeed";
const MAX_SAFE_INTEGER = BigInt(Number.MAX_SAFE_INTEGER);
const WIDTH_MAXIMA = {
  uint32: 4294967295n,
  uint53: 9007199254740991n,
  uint64: 18446744073709551615n,
};
const TIMINGS = new Set(["before_generation", "after_generation"]);
const QUEUE_ACTIONS = new Set(["fixed", "increment", "decrement", "randomize"]);
const DISTRIBUTIONS = new Set(["same", "increment", "decrement", "randomize"]);
const TARGET_INPUTS = new Set(["seed", "noise_seed", "seed_num"]);

function hasExactKeys(value, keys) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function parseSeed(value, maximum) {
  if (
    typeof value !== "string" ||
    !/^(0|[1-9][0-9]*)$/.test(value)
  ) {
    return null;
  }
  const parsed = BigInt(value);
  return parsed <= maximum ? parsed : null;
}

function validateEvent(value) {
  if (
    !hasExactKeys(value, [
      "controller_id",
      "seed_width",
      "timing",
      "queue_action",
      "distribution",
      "applied_seed",
      "next_value",
      "targets",
    ]) ||
    typeof value.controller_id !== "string" ||
    value.controller_id.length === 0 ||
    !Object.hasOwn(WIDTH_MAXIMA, value.seed_width) ||
    !TIMINGS.has(value.timing) ||
    !QUEUE_ACTIONS.has(value.queue_action) ||
    !DISTRIBUTIONS.has(value.distribution) ||
    !Array.isArray(value.targets)
  ) {
    return null;
  }

  const maximum = WIDTH_MAXIMA[value.seed_width];
  const appliedSeed = parseSeed(value.applied_seed, maximum);
  const nextValue = parseSeed(value.next_value, maximum);
  if (appliedSeed === null || nextValue === null) {
    return null;
  }

  const targets = [];
  for (const target of value.targets) {
    if (
      !hasExactKeys(target, ["node_id", "inputs"]) ||
      typeof target.node_id !== "string" ||
      target.node_id.length === 0 ||
      !Array.isArray(target.inputs)
    ) {
      return null;
    }
    const inputs = [];
    for (const input of target.inputs) {
      if (
        !hasExactKeys(input, ["name", "seed"]) ||
        !TARGET_INPUTS.has(input.name)
      ) {
        return null;
      }
      const seed = parseSeed(input.seed, maximum);
      if (seed === null) {
        return null;
      }
      inputs.push({ name: input.name, seed, seedText: input.seed });
    }
    targets.push({ nodeId: target.node_id, inputs });
  }

  return {
    controllerId: value.controller_id,
    appliedSeedText: value.applied_seed,
    nextValueText: value.next_value,
    targets,
  };
}

function findWidget(node, name) {
  return Array.isArray(node?.widgets)
    ? node.widgets.find((widget) => widget?.name === name)
    : undefined;
}

function resolveNode(nodeId) {
  // CRITICAL: execution IDs are root-relative instance paths, never leaf IDs.
  // Searching the active graph after a root miss can overwrite an unrelated seed.
  const graph = [app.rootGraph, app.graph, app.canvas?.graph].find(
    (value) => typeof value?.getNodeById === "function",
  );
  if (!graph || nodeId.length > 4096) {
    return undefined;
  }

  // Bound malformed/ambiguous graphs: at most 32 edges and 1024 lookup calls.
  const ancestors = new Set();
  let work = 0;
  let invalid = false;
  const lookup = (current, id) => {
    const ids = [id];
    if (/^(0|[1-9][0-9]*)$/.test(id) && Number.isSafeInteger(Number(id))) {
      ids.push(Number(id));
    }
    let found;
    for (const candidate of ids) {
      if (++work > 1024) {
        invalid = true;
        return undefined;
      }
      const node = current.getNodeById(candidate);
      if (node && found && node !== found) {
        invalid = true;
        return undefined;
      }
      if (node) found = node;
    }
    return found;
  };
  const visit = (current, id, depth) => {
    if (invalid) return undefined;
    if (depth > 32 || ancestors.has(current) || typeof current?.getNodeById !== "function") {
      invalid = true;
      return undefined;
    }
    ancestors.add(current);
    let resolved;
    try {
      for (let end = id.indexOf(":"); end !== -1; end = id.indexOf(":", end + 1)) {
        if (end === 0 || end === id.length - 1) continue;
        const host = lookup(current, id.slice(0, end));
        if (invalid) return undefined;
        if (typeof host?.isSubgraphNode !== "function" || !host.isSubgraphNode()) continue;
        const nested = visit(host.subgraph, id.slice(end + 1), depth + 1);
        if (invalid) return undefined;
        if (nested) {
          // Distinct valid instance paths are ambiguous even with a shared definition.
          if (resolved) {
            invalid = true;
            return undefined;
          }
          resolved = nested;
        }
      }
      // A verified path precedes a literal colon ID, matching host resolution.
      return resolved ?? lookup(current, id);
    } finally {
      ancestors.delete(current);
    }
  };
  try {
    const node = visit(graph, nodeId, 0);
    return invalid ? undefined : node;
  } catch {
    // Deleted or malformed host interfaces must not redirect writes elsewhere.
    return undefined;
  }
}

function setWidgetValue(node, name, value) {
  const widget = findWidget(node, name);
  if (!widget) {
    return false;
  }
  widget.value = value;
  widget.callback?.(value);
  node?.setDirtyCanvas?.(true, true);
  return true;
}

function applyReadback(event) {
  const payload = validateEvent(event?.detail);
  if (payload === null) {
    return;
  }

  const controller = resolveNode(payload.controllerId);
  setWidgetValue(controller, "value", payload.nextValueText);
  setWidgetValue(controller, "last_seed", payload.appliedSeedText);

  for (const target of payload.targets) {
    const node = resolveNode(target.nodeId);
    for (const input of target.inputs) {
      if (input.seed > MAX_SAFE_INTEGER) {
        continue;
      }
      setWidgetValue(node, input.name, Number(input.seed));
    }
  }
}

// Register immediately so readback is not coupled to extension setup ordering.
// The extension still uses the official registration surface and patches nothing.
api.addEventListener(EVENT_NAME, applyReadback);

app.registerExtension({
  name: EXTENSION_NAME,
});
