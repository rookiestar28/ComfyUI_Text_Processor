import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const extensionPath = path.join(repoRoot, "web", "global_random_seed.js");
const hostTiers = JSON.parse(
  await fs.readFile(
    path.join(repoRoot, "tests", "fixtures", "global_random_seed_host_tiers_v1.json"),
    "utf8",
  ),
).tiers;

async function loadExtension(page, tier, { invokeSetup = true } = {}) {
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
    } else if (url.pathname === "/scripts/api.js") {
      await route.fulfill({
        contentType: "text/javascript",
        body: "export const api = window.__host.api;",
      });
    } else if (
      url.pathname ===
      "/extensions/ComfyUI_Text_Processor/global_random_seed.js"
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
  await page.evaluate(({ tierId, shouldInvokeSetup }) => {
    const nodes = new Map();
    const listeners = new Map();
    const extensions = [];
    window.__host = {
      tierId,
      nodes,
      listeners,
      extensions,
      app: {
        graph: {
          getNodeById(id) {
            return nodes.get(id);
          },
        },
        registerExtension(extension) {
          extensions.push(extension);
          if (shouldInvokeSetup) {
            extension.setup?.();
          }
        },
        queuePrompt() {},
        graphToPrompt() {},
      },
      api: {
        addEventListener(name, handler) {
          listeners.set(name, handler);
        },
      },
    };
    window.__makeNode = (id, values) => {
      const hostId = tierId === "desktop_floor" ? Number(id) : String(id);
      const node = {
        id: hostId,
        widgets: Object.entries(values).map(([name, value]) => ({
          name,
          value,
          callbackCount: 0,
          callback() {
            this.callbackCount += 1;
          },
        })),
      };
      nodes.set(hostId, node);
      return node;
    };
    window.__dispatchSeed = (detail) => {
      const handler = listeners.get("text-processor-global-random-seed");
      handler?.({ detail });
    };
  }, { tierId: tier.id, shouldInvokeSetup: invokeSetup });

  await page.evaluate(() => {
    window.__protectedBefore = {
      queuePrompt: window.__host.app.queuePrompt,
      graphToPrompt: window.__host.app.graphToPrompt,
      getNodeById: window.__host.app.graph.getNodeById,
    };
  });
  await page.evaluate(() =>
    import(
      "https://host.test/extensions/ComfyUI_Text_Processor/global_random_seed.js"
    ),
  );
}

test("readback listener is active immediately when the module loads", async ({
  page,
}) => {
  await loadExtension(page, hostTiers[1], { invokeSetup: false });
  const listenerNames = await page.evaluate(() => [
    ...window.__host.listeners.keys(),
  ]);
  expect(listenerNames).toEqual(["text-processor-global-random-seed"]);
});

function eventPayload(overrides = {}) {
  return {
    controller_id: "1",
    seed_width: "uint32",
    timing: "before_generation",
    queue_action: "fixed",
    distribution: "same",
    applied_seed: "4294967295",
    next_value: "4294967295",
    targets: [
      {
        node_id: "2",
        inputs: [{ name: "seed", seed: "4294967295" }],
      },
    ],
    ...overrides,
  };
}

for (const tier of hostTiers) {
  test(`${tier.id}: official extension registration preserves host methods`, async ({
    page,
  }) => {
    await loadExtension(page, tier);
    const result = await page.evaluate(() => ({
      extensionNames: window.__host.extensions.map((entry) => entry.name),
      listenerNames: [...window.__host.listeners.keys()],
      methodsPreserved:
        window.__host.app.queuePrompt === window.__protectedBefore.queuePrompt &&
        window.__host.app.graphToPrompt === window.__protectedBefore.graphToPrompt &&
        window.__host.app.graph.getNodeById ===
          window.__protectedBefore.getNodeById,
    }));
    expect(result.extensionNames).toEqual([
      "ComfyUI.TextProcessor.GlobalRandomSeed",
    ]);
    expect(result.listenerNames).toEqual([
      "text-processor-global-random-seed",
    ]);
    expect(result.methodsPreserved).toBe(true);
  });
}

test("safe uint32 event updates controller strings and exact target widget", async ({
  page,
}) => {
  await loadExtension(page, hostTiers[1]);
  const result = await page.evaluate((payload) => {
    const controller = window.__makeNode("1", { value: "0", last_seed: "0" });
    const target = window.__makeNode("2", { seed: 7, other: 9 });
    window.__dispatchSeed(payload);
    return {
      controller: Object.fromEntries(
        controller.widgets.map((widget) => [widget.name, widget.value]),
      ),
      target: Object.fromEntries(
        target.widgets.map((widget) => [widget.name, widget.value]),
      ),
      controllerCallbacks: controller.widgets.map(
        (widget) => widget.callbackCount,
      ),
      targetCallbacks: target.widgets.map((widget) => widget.callbackCount),
    };
  }, eventPayload());
  expect(result.controller).toEqual({
    value: "4294967295",
    last_seed: "4294967295",
  });
  expect(result.target).toEqual({ seed: 4294967295, other: 9 });
  expect(result.controllerCallbacks).toEqual([1, 1]);
  expect(result.targetCallbacks).toEqual([1, 0]);
});

test("desktop floor resolves numeric LiteGraph node IDs", async ({ page }) => {
  await loadExtension(page, hostTiers[0]);
  const result = await page.evaluate((payload) => {
    const controller = window.__makeNode("1", { value: "0", last_seed: "0" });
    const target = window.__makeNode("2", { seed: 7 });
    window.__dispatchSeed(payload);
    return {
      controller: controller.widgets.map((widget) => widget.value),
      seed: target.widgets[0].value,
    };
  }, eventPayload());
  expect(result).toEqual({
    controller: ["4294967295", "4294967295"],
    seed: 4294967295,
  });
});

test("unsafe uint64 keeps target numeric widget unchanged without rounding", async ({
  page,
}) => {
  await loadExtension(page, hostTiers[1]);
  const maximum = "18446744073709551615";
  const result = await page.evaluate((payload) => {
    const controller = window.__makeNode("1", { value: "0", last_seed: "0" });
    const target = window.__makeNode("2", { seed: 17 });
    window.__dispatchSeed(payload);
    return {
      controller: Object.fromEntries(
        controller.widgets.map((widget) => [widget.name, widget.value]),
      ),
      seed: target.widgets[0].value,
    };
  }, eventPayload({
    seed_width: "uint64",
    applied_seed: maximum,
    next_value: maximum,
    targets: [
      {
        node_id: "2",
        inputs: [{ name: "seed", seed: maximum }],
      },
    ],
  }));
  expect(result.controller).toEqual({ value: maximum, last_seed: maximum });
  expect(result.seed).toBe(17);
});

test("malformed or unrelated event data makes no UI change", async ({ page }) => {
  await loadExtension(page, hostTiers[0]);
  const result = await page.evaluate(() => {
    const controller = window.__makeNode("1", { value: "5", last_seed: "4" });
    const target = window.__makeNode("2", { seed: 3 });
    window.__dispatchSeed({
      controller_id: "1",
      applied_seed: "1e9",
      next_value: "-1",
      targets: [{ node_id: "2", inputs: [{ name: "other", seed: "8" }] }],
    });
    return {
      controller: controller.widgets.map((widget) => widget.value),
      seed: target.widgets[0].value,
    };
  });
  expect(result).toEqual({ controller: ["5", "4"], seed: 3 });
});
