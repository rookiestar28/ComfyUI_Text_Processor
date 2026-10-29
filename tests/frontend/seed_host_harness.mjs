import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const extensionPath = path.join(repoRoot, "web", "global_random_seed.js");
export async function loadExtension(page, tier, { invokeSetup = true } = {}) {
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
  await page.evaluate(({ tierId, widgetFacade, shouldInvokeSetup }) => {
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
        widgets: Object.entries(values).map(([name, value]) => {
          const state = { value };
          return ({
          name,
          value,
          state,
          callbackCount: 0,
          callback() {
            this.callbackCount += 1;
          },
        });
        }).map((widget) => {
          if (widgetFacade === "state_backed") Object.defineProperty(widget, "value", {
            get() { return this.state.value; },
            set(next) { this.state.value = next; },
          });
          return widget;
        }),
      };
      nodes.set(hostId, node);
      return node;
    };
    window.__dispatchSeed = (detail) => {
      const handler = listeners.get("text-processor-global-random-seed");
      handler?.({ detail });
    };
  }, { tierId: tier.id, widgetFacade: tier.widget_facade, shouldInvokeSetup: invokeSetup });

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

export function eventPayload(overrides = {}) {
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

