import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "ComfyUI.TextProcessor.AdvancedResolutionSelectorRuntimeLabels";
const NODE_ID = "TP_AdvancedResolutionSelector";
const UI_KEY = "tp_advanced_resolution";
const TARGET_OUTPUTS = Object.freeze(["width", "height"]);
const NODE_STATE = new WeakMap();
const WRAPPED_NODE_TYPES = new WeakSet();

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function hasExactKeys(value, expectedKeys) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function readDimensions(output) {
  try {
    if (!output || typeof output !== "object" || Array.isArray(output)) {
      return null;
    }
    const entries = output[UI_KEY];
    if (!Array.isArray(entries) || entries.length === 0) {
      return null;
    }
    const finalEntry = entries[entries.length - 1];
    if (!hasExactKeys(finalEntry, TARGET_OUTPUTS)) {
      return null;
    }
    if (
      !Number.isSafeInteger(finalEntry.width) ||
      finalEntry.width <= 0 ||
      !Number.isSafeInteger(finalEntry.height) ||
      finalEntry.height <= 0
    ) {
      return null;
    }
    return { width: finalEntry.width, height: finalEntry.height };
  } catch (_error) {
    return null;
  }
}

function outputSlots(node) {
  if (!Array.isArray(node?.outputs)) {
    return null;
  }
  const slots = Object.fromEntries(
    TARGET_OUTPUTS.map((name) => [
      name,
      node.outputs.find((slot) => slot?.name === name),
    ]),
  );
  return TARGET_OUTPUTS.every((name) => slots[name]) ? slots : null;
}

function labelSnapshot(slot) {
  return hasOwn(slot, "label")
    ? { present: true, value: slot.label }
    : { present: false, value: undefined };
}

function captureSlotLabels(state, slots) {
  for (const name of TARGET_OUTPUTS) {
    state.baseLabels.set(name, labelSnapshot(slots[name]));
  }
  state.baseCaptured = true;
}

function captureSerializedLabels(state, serialised) {
  if (!Array.isArray(serialised?.outputs)) {
    return false;
  }
  const entries = Object.fromEntries(
    TARGET_OUTPUTS.map((name) => [
      name,
      serialised.outputs.find((entry) => entry?.name === name),
    ]),
  );
  if (!TARGET_OUTPUTS.every((name) => entries[name])) {
    return false;
  }
  for (const name of TARGET_OUTPUTS) {
    state.baseLabels.set(name, labelSnapshot(entries[name]));
  }
  state.baseCaptured = true;
  return true;
}

function createState() {
  return {
    baseCaptured: false,
    baseLabels: new Map(),
    generatedLabels: null,
    latest: null,
  };
}

function stateFor(node) {
  if (!node || typeof node !== "object") {
    return null;
  }
  let state = NODE_STATE.get(node);
  if (!state) {
    state = createState();
    NODE_STATE.set(node, state);
  }
  return state;
}

function preserveUserLabels(state, slots) {
  if (!state.generatedLabels) {
    return;
  }
  for (const name of TARGET_OUTPUTS) {
    const generated = state.generatedLabels.get(name);
    if (slots[name].label !== generated) {
      state.baseLabels.set(name, labelSnapshot(slots[name]));
    }
  }
}

function refreshLabels(node) {
  try {
    node.setDirtyCanvas?.(true, true);
  } catch (_error) {
    // A renderer refresh is best-effort; it must not affect node execution.
  }
  try {
    node.graph?.trigger?.("node:slot-label:changed", { nodeId: node.id });
  } catch (_error) {
    // A renderer refresh is best-effort; it must not affect node execution.
  }
}

function applyDimensions(node, dimensions) {
  const slots = outputSlots(node);
  if (!slots) {
    return false;
  }
  const state = stateFor(node);
  if (!state) {
    return false;
  }
  if (!state.baseCaptured || !state.generatedLabels) {
    captureSlotLabels(state, slots);
  } else {
    preserveUserLabels(state, slots);
  }

  const generatedLabels = new Map([
    ["width", `width: ${dimensions.width}`],
    ["height", `height: ${dimensions.height}`],
  ]);
  slots.width.label = generatedLabels.get("width");
  slots.height.label = generatedLabels.get("height");
  state.generatedLabels = generatedLabels;
  state.latest = dimensions;
  refreshLabels(node);
  return true;
}

function sanitiseSerializedOutputs(node, serialised) {
  const state = NODE_STATE.get(node);
  if (!state?.latest || !Array.isArray(serialised?.outputs)) {
    return;
  }
  const slots = outputSlots(node);
  if (slots) {
    preserveUserLabels(state, slots);
  }
  for (const entry of serialised.outputs) {
    const name = entry?.name;
    if (!TARGET_OUTPUTS.includes(name)) {
      continue;
    }
    const base = state.baseLabels.get(name);
    if (base?.present) {
      entry.label = base.value;
    } else {
      delete entry.label;
    }
  }
}

function wrapTargetNode(nodeType, nodeData) {
  if (
    !nodeType?.prototype ||
    nodeData?.name !== NODE_ID ||
    WRAPPED_NODE_TYPES.has(nodeType)
  ) {
    return;
  }

  const prototype = nodeType.prototype;
  const originalOnExecuted = prototype.onExecuted;
  const originalOnConfigure = prototype.onConfigure;
  const originalOnSerialize = prototype.onSerialize;

  prototype.onExecuted = function onExecutedWrapper(...args) {
    const originalResult =
      typeof originalOnExecuted === "function"
        ? originalOnExecuted.apply(this, args)
        : undefined;
    const dimensions = readDimensions(args[0]);
    if (dimensions) {
      applyDimensions(this, dimensions);
    }
    return originalResult;
  };

  prototype.onConfigure = function onConfigureWrapper(...args) {
    const originalResult =
      typeof originalOnConfigure === "function"
        ? originalOnConfigure.apply(this, args)
        : undefined;
    const state = stateFor(this);
    if (state) {
      state.baseCaptured = false;
      state.baseLabels.clear();
      state.generatedLabels = null;
      state.latest = null;
      const slots = outputSlots(this);
      if (slots) {
        captureSlotLabels(state, slots);
      } else {
        captureSerializedLabels(state, args[0]);
      }
    }
    return originalResult;
  };

  prototype.onSerialize = function onSerializeWrapper(...args) {
    const originalResult =
      typeof originalOnSerialize === "function"
        ? originalOnSerialize.apply(this, args)
        : undefined;
    sanitiseSerializedOutputs(this, args[0]);
    return originalResult;
  };

  WRAPPED_NODE_TYPES.add(nodeType);
}

app.registerExtension({
  name: EXTENSION_NAME,
  beforeRegisterNodeDef(nodeType, nodeData) {
    wrapTargetNode(nodeType, nodeData);
  },
});
