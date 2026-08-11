import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";


const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const extensionPath = path.join(repoRoot, "web", "advanced_resolution_selector.js");
const contract = JSON.parse(
  await fs.readFile(
    path.join(
      repoRoot,
      "tests",
      "fixtures",
      "advanced_resolution_selector_runtime_labels_v1.json",
    ),
    "utf8",
  ),
);


async function loadExtension(page, tierId) {
  const extensionSource = await fs.readFile(extensionPath, "utf8");
  await page.route("https://host.test/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/") {
      await route.fulfill({
        contentType: "text/html",
        body: "<!doctype html><title>synthetic host</title>",
      });
    } else if (url.pathname === "/scripts/app.js") {
      await route.fulfill({
        contentType: "text/javascript",
        body: "export const app = window.__host.app;",
      });
    } else if (
      url.pathname ===
      "/extensions/ComfyUI_Text_Processor/advanced_resolution_selector.js"
    ) {
      await route.fulfill({
        contentType: "text/javascript",
        body: extensionSource,
      });
    } else {
      await route.abort();
    }
  });

  await page.goto("https://host.test/");
  await page.evaluate(({ selectedTier }) => {
    const extensions = [];
    const protectedMethods = {
      queuePrompt() {},
      graphToPrompt() {},
    };
    window.__host = {
      selectedTier,
      extensions,
      app: {
        graph: {},
        rootGraph: {},
        ...protectedMethods,
        registerExtension(extension) {
          extensions.push(extension);
        },
      },
    };
    window.__registerNodeType = (nodeData, options = {}) => {
      class SyntheticNode {}
      SyntheticNode.prototype.onExecuted = function onExecuted(payload) {
        this.originalExecutedCalls = (this.originalExecutedCalls ?? 0) + 1;
        this.originalPayload = payload;
        return "original-executed";
      };
      SyntheticNode.prototype.onConfigure = function onConfigure(config) {
        this.originalConfigureCalls = (this.originalConfigureCalls ?? 0) + 1;
        this.originalConfig = config;
        return "original-configure";
      };
      SyntheticNode.prototype.onSerialize = function onSerialize(serialised) {
        this.originalSerializeCalls = (this.originalSerializeCalls ?? 0) + 1;
        serialised.originalHook = true;
        return "original-serialize";
      };
      const extension = extensions[0];
      extension.beforeRegisterNodeDef(SyntheticNode, nodeData);
      const node = new SyntheticNode();
      node.id = options.id ?? "node-1";
      const slot = (name, label, hasLabel = true) => {
        const value = { name, type: "INT", links: [7], index: name === "width" ? 0 : 1 };
        if (hasLabel) {
          value.label = label;
        }
        return value;
      };
      node.outputs = [];
      if (!options.missingWidth) {
        node.outputs.push(slot("width", options.widthLabel ?? "width", !options.absentWidth));
      }
      if (!options.missingHeight) {
        node.outputs.push(slot("height", options.heightLabel ?? "height", !options.absentHeight));
      }
      node.outputs.push(slot("other", "other"));
      node.graph = {
        events: [],
        trigger(name, payload) {
          this.events.push({ name, payload });
        },
      };
      node.dirtyCalls = [];
      node.setDirtyCanvas = (...args) => node.dirtyCalls.push(args);
      return node;
    };
  }, { selectedTier: tierId });

  await page.evaluate(() =>
    import(
      "https://host.test/extensions/ComfyUI_Text_Processor/advanced_resolution_selector.js"
    ),
  );
}


test("registers the exact extension without changing protected host methods", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => ({
    names: window.__host.extensions.map((extension) => extension.name),
    queuePrompt: window.__host.app.queuePrompt.name,
    graphToPrompt: window.__host.app.graphToPrompt.name,
  }));
  expect(result).toEqual({
    names: [contract.extension_name],
    queuePrompt: "queuePrompt",
    graphToPrompt: "graphToPrompt",
  });
});


for (const tierId of Object.keys(contract.tiers)) {
  test(`${tierId}: valid and cached UI output updates both labels and refreshes both renderers`, async ({
    page,
  }) => {
    await loadExtension(page, tierId);
    const result = await page.evaluate(() => {
      const payload = (width, height) => ({
        tp_advanced_resolution: [{ width, height }],
      });
      const node = window.__registerNodeType({ name: "TP_AdvancedResolutionSelector" }, {
        absentWidth: true,
        heightLabel: "base height",
      });
      node.onConfigure({ outputs: structuredClone(node.outputs) });
      const firstReturn = node.onExecuted(payload(1344, 768));
      const cachedReturn = node.onExecuted(payload(1536, 864));
      const serialised = {
        outputs: structuredClone(node.outputs),
        widgets_values: ["fixed", "1:1", "landscape", 1, 1, 1.0, 8, 0],
        links: [[1, 2]],
      };
      const serializeReturn = node.onSerialize(serialised);
      return {
        labels: node.outputs.slice(0, 2).map((slot) => slot.label),
        firstReturn,
        cachedReturn,
        dirtyCalls: node.dirtyCalls,
        events: node.graph.events,
        originalCalls: {
          executed: node.originalExecutedCalls,
          configure: node.originalConfigureCalls,
          serialize: node.originalSerializeCalls,
        },
        serializeReturn,
        serialised,
        liveLabels: node.outputs.slice(0, 2).map((slot) => slot.label),
      };
    });
    expect(result.labels).toEqual(["width: 1536", "height: 864"]);
    expect(result.firstReturn).toBe("original-executed");
    expect(result.cachedReturn).toBe("original-executed");
    expect(result.dirtyCalls).toEqual([[true, true], [true, true]]);
    expect(result.events).toEqual([
      { name: "node:slot-label:changed", payload: { nodeId: "node-1" } },
      { name: "node:slot-label:changed", payload: { nodeId: "node-1" } },
    ]);
    expect(result.originalCalls).toEqual({ executed: 2, configure: 1, serialize: 1 });
    expect(result.serializeReturn).toBe("original-serialize");
    expect(result.serialised.originalHook).toBe(true);
    expect(result.serialised.outputs[0]).not.toHaveProperty("label");
    expect(result.serialised.outputs[1].label).toBe("base height");
    expect(result.serialised.widgets_values).toHaveLength(8);
    expect(result.serialised.links).toEqual([[1, 2]]);
    expect(result.liveLabels).toEqual(["width: 1536", "height: 864"]);
  });
}


for (const tierId of Object.keys(contract.tiers)) {
  test(`${tierId}: comparable synthetic baseline and runtime label captures`, async ({
    page,
  }) => {
    await loadExtension(page, tierId);
    await page.setViewportSize({ width: 800, height: 600 });
    const captureRoot = path.join(repoRoot, ".tmp", "f23-visual");
    await fs.mkdir(captureRoot, { recursive: true });
    await page.evaluate(() => {
      const node = window.__registerNodeType({ name: "TP_AdvancedResolutionSelector" });
      window.__visualNode = node;
      const panel = document.createElement("section");
      panel.id = "synthetic-resolution-output";
      panel.style.cssText = [
        "width: 420px",
        "padding: 28px",
        "background: #18202a",
        "color: #f4f7fb",
        "font: 20px sans-serif",
      ].join(";");
      document.body.replaceChildren(panel);
      for (const name of ["width", "height"]) {
        const row = document.createElement("div");
        row.dataset.output = name;
        row.style.cssText = [
          "display: flex",
          "align-items: center",
          "gap: 8px",
          "padding: 12px 0",
          "border-bottom: 1px solid #465466",
        ].join(";");
        const label = document.createElement("span");
        label.dataset.outputLabel = name;
        label.textContent = node.outputs.find((slot) => slot.name === name)?.label ?? name;
        const dot = document.createElement("span");
        dot.dataset.outputDot = name;
        dot.textContent = "●";
        dot.setAttribute("aria-label", `${name} output connection`);
        dot.style.color = "#78c8ff";
        row.append(label, dot);
        panel.append(row);
      }
    });
    await page.screenshot({
      path: path.join(captureRoot, `${tierId}-baseline.png`),
      fullPage: true,
    });
    await page.evaluate(() => {
      const node = window.__visualNode;
      node.onExecuted({ tp_advanced_resolution: [{ width: 1344, height: 768 }] });
      for (const name of ["width", "height"]) {
        const label = document.querySelector(`[data-output-label="${name}"]`);
        label.textContent = node.outputs.find((slot) => slot.name === name)?.label ?? name;
      }
    });
    await page.screenshot({
      path: path.join(captureRoot, `${tierId}-runtime.png`),
      fullPage: true,
    });
    const labels = await page.evaluate(() =>
      ["width", "height"].map(
        (name) => document.querySelector(`[data-output-label="${name}"]`)?.textContent,
      ),
    );
    expect(labels).toEqual(["width: 1344", "height: 768"]);
  });
}


test("strict payload validation ignores malformed data and keeps the last valid labels", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => {
    const payload = (width, height) => ({
      tp_advanced_resolution: [{ width, height }],
    });
    const node = window.__registerNodeType({ name: "TP_AdvancedResolutionSelector" });
    node.onExecuted(payload(1200, 800));
    const invalidPayloads = [
      null,
      {},
      { tp_advanced_resolution: [] },
      { tp_advanced_resolution: [{ width: 1, height: 2, extra: 3 }] },
      { tp_advanced_resolution: [{ width: 1 }] },
      { tp_advanced_resolution: [{ width: 1, height: 2 }, "bad"] },
      { tp_advanced_resolution: [{ width: 1.5, height: 2 }] },
      { tp_advanced_resolution: [{ width: 0, height: 2 }] },
      { tp_advanced_resolution: [{ width: -1, height: 2 }] },
      { tp_advanced_resolution: [{ width: Number.MAX_SAFE_INTEGER + 1, height: 2 }] },
      { tp_advanced_resolution: [{ width: true, height: 2 }] },
      { tp_advanced_resolution: [{ width: 1, height: Infinity }] },
    ];
    for (const payload of invalidPayloads) {
      node.onExecuted(payload);
    }
    return {
      labels: node.outputs.slice(0, 2).map((slot) => slot.label),
      dirtyCount: node.dirtyCalls.length,
      eventCount: node.graph.events.length,
      originalCalls: node.originalExecutedCalls,
    };
  });
  expect(result.labels).toEqual(["width: 1200", "height: 800"]);
  expect(result.dirtyCount).toBe(1);
  expect(result.eventCount).toBe(1);
  expect(result.originalCalls).toBe(13);
});


test("final list entry is used and missing ports cannot partially update labels", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => {
    const payload = (width, height) => ({
      tp_advanced_resolution: [{ width, height }],
    });
    const full = window.__registerNodeType({ name: "TP_AdvancedResolutionSelector" });
    full.onExecuted({
      tp_advanced_resolution: [
        { width: 1, height: 2 },
        { width: 3, height: 4 },
      ],
    });
    const missing = window.__registerNodeType(
      { name: "TP_AdvancedResolutionSelector" },
      { missingHeight: true, widthLabel: "static width" },
    );
    missing.onExecuted(payload(300, 200));
    return {
      full: full.outputs.slice(0, 2).map((slot) => slot.label),
      missing: missing.outputs.map((slot) => slot.label),
      missingDirty: missing.dirtyCalls.length,
      missingEvents: missing.graph.events.length,
    };
  });
  expect(result.full).toEqual(["width: 3", "height: 4"]);
  expect(result.missing).toEqual(["static width", "other"]);
  expect(result.missingDirty).toBe(0);
  expect(result.missingEvents).toBe(0);
});


test("custom labels changed after execution are preserved while generated labels stay out of serialization", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => {
    const node = window.__registerNodeType({
      name: "TP_AdvancedResolutionSelector",
    }, {
      widthLabel: "base width",
      heightLabel: "base height",
    });
    node.onConfigure({ outputs: structuredClone(node.outputs) });
    node.onExecuted({ tp_advanced_resolution: [{ width: 640, height: 480 }] });
    node.outputs.find((slot) => slot.name === "width").label = "user width";
    node.outputs.find((slot) => slot.name === "height").label = "user height";
    const serialised = { outputs: structuredClone(node.outputs) };
    node.onSerialize(serialised);
    return {
      labels: serialised.outputs.slice(0, 2).map((slot) => slot.label),
      generatedPresent: JSON.stringify(serialised).includes("width: 640") ||
        JSON.stringify(serialised).includes("height: 480"),
      live: node.outputs.slice(0, 2).map((slot) => slot.label),
    };
  });
  expect(result.labels).toEqual(["user width", "user height"]);
  expect(result.generatedPresent).toBe(false);
  expect(result.live).toEqual(["user width", "user height"]);
});


test("a base label changed before the first execution becomes the preserved label", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => {
    const node = window.__registerNodeType({ name: "TP_AdvancedResolutionSelector" });
    node.onConfigure({ outputs: structuredClone(node.outputs) });
    node.outputs.find((slot) => slot.name === "width").label = "pre-execution width";
    node.onExecuted({ tp_advanced_resolution: [{ width: 512, height: 512 }] });
    const serialised = { outputs: structuredClone(node.outputs) };
    node.onSerialize(serialised);
    return serialised.outputs.slice(0, 2).map((slot) => slot.label);
  });
  expect(result).toEqual(["pre-execution width", "height"]);
});


test("unrelated nodes are not wrapped", async ({ page }) => {
  await loadExtension(page, "current");
  const result = await page.evaluate(() => {
    const node = window.__registerNodeType({ name: "OtherNode" });
    const returnValue = node.onExecuted({
      tp_advanced_resolution: [{ width: 99, height: 77 }],
    });
    return {
      labels: node.outputs.slice(0, 2).map((slot) => slot.label),
      returnValue,
      dirtyCount: node.dirtyCalls.length,
      originalCalls: node.originalExecutedCalls,
    };
  });
  expect(result).toEqual({
    labels: ["width", "height"],
    returnValue: "original-executed",
    dirtyCount: 0,
    originalCalls: 1,
  });
});
