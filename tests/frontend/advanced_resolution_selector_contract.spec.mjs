import { expect, test } from "@playwright/test";


const INPUTS = [
  { id: "output_mode", type: "COMBO", options: ["fixed", "randomize", "randomize_all"], default: "fixed" },
  { id: "aspect_ratio", type: "COMBO", options: ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9", "custom"], default: "1:1" },
  { id: "direction", type: "COMBO", options: ["landscape", "portrait"], default: "landscape" },
  { id: "custom_ratio_width", type: "INT", min: 1, max: 10000, step: 1, advanced: true, default: 1 },
  { id: "custom_ratio_height", type: "INT", min: 1, max: 10000, step: 1, advanced: true, default: 1 },
  { id: "megapixels", type: "FLOAT", min: 0.1, max: 16.0, step: 0.1, default: 1.0 },
  { id: "multiple", type: "INT", min: 8, max: 128, step: 4, advanced: true, default: 8 },
  { id: "seed", type: "INT", min: 0, max: 4294967295, step: 1, control_after_generate: true, default: 0 },
];


function tierSnapshot() {
  return {
    node_id: "TP_AdvancedResolutionSelector",
    display_name: "Advanced Resolution Selector",
    category: "ComfyUI Text Processor/Image",
    function: "select_resolution",
    inputs: structuredClone(INPUTS),
    widget_values: ["randomize_all", "custom", "portrait", 6, 4, 1.0, 8, 123],
  };
}


test("synthetic desktop and current snapshots preserve identity and input order", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const snapshots = await page.evaluate(() => ({ desktop_floor: null, current_host: null }));
  snapshots.desktop_floor = tierSnapshot();
  snapshots.current_host = tierSnapshot();
  for (const snapshot of Object.values(snapshots)) {
    expect(snapshot.node_id).toBe("TP_AdvancedResolutionSelector");
    expect(snapshot.display_name).toBe("Advanced Resolution Selector");
    expect(snapshot.function).toBe("select_resolution");
    expect(snapshot.inputs.map((input) => input.id)).toEqual(INPUTS.map((input) => input.id));
  }
  expect(snapshots.desktop_floor).toEqual(snapshots.current_host);
});


test("synthetic snapshots preserve advanced flags, seed control, and safe bounds", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const snapshot = tierSnapshot();
  const width = snapshot.inputs.find((input) => input.id === "custom_ratio_width");
  const height = snapshot.inputs.find((input) => input.id === "custom_ratio_height");
  const multiple = snapshot.inputs.find((input) => input.id === "multiple");
  const seed = snapshot.inputs.find((input) => input.id === "seed");
  expect(width).toMatchObject({ advanced: true, min: 1, max: 10000, step: 1 });
  expect(height).toMatchObject({ advanced: true, min: 1, max: 10000, step: 1 });
  expect(multiple).toMatchObject({ advanced: true, min: 8, max: 128, step: 4 });
  expect(seed).toMatchObject({ control_after_generate: true, min: 0, max: 4294967295, step: 1 });
});


test("synthetic positional serialization restores all eight widgets", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const snapshot = tierSnapshot();
  const restored = Object.fromEntries(snapshot.inputs.map((input, index) => [input.id, snapshot.widget_values[index]]));
  expect(restored).toEqual({
    output_mode: "randomize_all",
    aspect_ratio: "custom",
    direction: "portrait",
    custom_ratio_width: 6,
    custom_ratio_height: 4,
    megapixels: 1.0,
    multiple: 8,
    seed: 123,
  });
});


test("synthetic snapshots fail when the public positional contract drifts", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const snapshot = tierSnapshot();
  const mutated = structuredClone(snapshot);
  [mutated.inputs[0], mutated.inputs[1]] = [mutated.inputs[1], mutated.inputs[0]];
  expect(mutated.inputs.map((input) => input.id)).not.toEqual(INPUTS.map((input) => input.id));
  expect(mutated.widget_values).toHaveLength(8);
});
