// Offline facades derived from pinned sources; no upstream host code executes.
import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import { loadExtension, eventPayload } from "./seed_host_harness.mjs";

const matrix = JSON.parse(await fs.readFile(new URL("../fixtures/host_compatibility_matrix_v1.json", import.meta.url), "utf8"));

for (const tier of matrix.tiers) {
  test(`${tier.id}: restored text and numeric state reaches queued values with held registration`, async ({ page }) => {
    await loadExtension(page, tier, { invokeSetup: false });
    await page.evaluate(() => {
      const controller = window.__makeNode("1", { value: "0", last_seed: "0" });
      const target = window.__makeNode("2", { seed: 0 });
      const input = document.createElement("input");
      input.id = "seed";
      input.value = controller.widgets[0].value;
      input.addEventListener("change", () => { controller.widgets[0].value = input.value; });
      document.body.append(input);
      // Restore uses each widget's public value setter; text seeds stay text.
      target.widgets[0].value = Number("17");
      window.__queueValues = () => [
        controller.widgets.map((widget) => widget.value),
        target.widgets.map((widget) => widget.value),
      ];
    });
    await page.locator("#seed").fill("9007199254740991");
    await page.locator("#seed").press("Tab");
    expect(await page.evaluate(() => window.__queueValues())).toEqual([["9007199254740991", "0"], [17]]);
    const maximum = "9007199254740991";
    const payload = eventPayload({ seed_width: "uint53", applied_seed: maximum, next_value: maximum,
      targets: [{ node_id: "2", inputs: [{ name: "seed", seed: maximum }] }] });
    await page.evaluate((detail) => window.__dispatchSeed(detail), payload);
    const result = await page.evaluate(() => ({
      queue: window.__queueValues(),
      callbacks: [...window.__host.nodes.values()].flatMap((node) => node.widgets.map((widget) => widget.callbackCount)),
      state: [...window.__host.nodes.values()].flatMap((node) => node.widgets.map((widget) => widget.state.value)),
    }));
    expect(result.queue).toEqual([[maximum, maximum], [Number(maximum)]]);
    expect(result.callbacks).toEqual([1, 1, 1]);
    if (tier.widget_facade === "state_backed") expect(result.state).toEqual([maximum, maximum, Number(maximum)]);
    // Negative control: invalid precision must not alter the accepted queued state.
    await page.evaluate((detail) => window.__dispatchSeed(detail), { ...payload, applied_seed: "9007199254740992" });
    expect(await page.evaluate(() => window.__queueValues())).toEqual(result.queue);
    expect(result.queue).not.toEqual([[Number(maximum), maximum], [Number(maximum)]]);
  });
}
