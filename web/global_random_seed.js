import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const EVENT_NAME = "text-processor-global-random-seed";
const EXTENSION_NAME = "ComfyUI.TextProcessor.GlobalRandomSeed";
const MAX_SAFE_INTEGER = BigInt(Number.MAX_SAFE_INTEGER);
const WIDTH_MAXIMA = {
  uint32: 4294967295n,
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
  const candidates = [nodeId];
  if (/^(0|[1-9][0-9]*)$/.test(nodeId)) {
    const numericId = Number(nodeId);
    if (Number.isSafeInteger(numericId)) {
      candidates.push(numericId);
    }
  }

  const graphs = [app.rootGraph, app.graph, app.canvas?.graph];
  const visited = new Set();
  for (const graph of graphs) {
    if (!graph || visited.has(graph) || typeof graph.getNodeById !== "function") {
      continue;
    }
    visited.add(graph);
    for (const candidate of candidates) {
      const node = graph.getNodeById(candidate);
      if (node) {
        return node;
      }
    }
  }
  return undefined;
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
