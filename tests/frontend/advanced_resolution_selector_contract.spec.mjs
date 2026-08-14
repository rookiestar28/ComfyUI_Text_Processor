import { expect, test } from "@playwright/test";
import fs from "node:fs";


const MIGRATION_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_legacy_migration_v2.json",
  import.meta.url,
);


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


function loadMigrationFixture() {
  expect(
    fs.existsSync(MIGRATION_FIXTURE_PATH),
    "required v2 fixture is missing: advanced_resolution_selector_legacy_migration_v2.json",
  ).toBeTruthy();
  return JSON.parse(fs.readFileSync(MIGRATION_FIXTURE_PATH, "utf8"));
}


function restoreAndSerializeLegacyValue(fixture, tier, serializer = null) {
  expect(fixture.schema_version).toBe(2);
  expect(fixture.contract).toBe("advanced_resolution_selector_legacy_migration");
  expect(fixture.synthetic_only).toBe(true);
  expect(fixture.node_id).toBe("TP_AdvancedResolutionSelector");
  expect(tier.source).toBe("synthetic_pinned_source_contract");
  expect(fixture.input_ids).toEqual(INPUTS.map((input) => input.id));
  expect(fixture.selectable_aspect_ratios).toEqual([
    "1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "custom",
  ]);
  expect(fixture.selectable_aspect_ratios).not.toContain("21:9");
  expect(fixture.widget_values).toHaveLength(fixture.input_ids.length);

  const restored = Object.fromEntries(
    fixture.input_ids.map((inputId, index) => [inputId, fixture.widget_values[index]]),
  );
  expect(restored.aspect_ratio).toBe("21:9");

  const serialize = serializer ?? ((state) => fixture.input_ids.map((inputId) => state[inputId]));
  const serialized = serialize(restored);
  expect(serialized).toHaveLength(fixture.input_ids.length);
  expect(serialized[1]).toBe("21:9");
  expect(serialized).toEqual(fixture.widget_values);
  return { restored, serialized };
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


test("floor and current synthetic tiers restore and serialize unavailable legacy 21:9", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const fixture = loadMigrationFixture();
  expect(fixture.frontend_tiers).toEqual([
    { id: "desktop_floor", source: "synthetic_pinned_source_contract", version: "1.43.18" },
    { id: "current_reference", source: "synthetic_pinned_source_contract", version: "1.49.1" },
  ]);
  expect(fixture.custom_ratio_presentation).toEqual({
    custom_ratio_height: {
      label: "custom_ratio_height",
      tooltip: "Positive custom ratio height; used when aspect_ratio is custom.",
    },
    custom_ratio_width: {
      label: "custom_ratio_width",
      tooltip: "Positive custom ratio width; used when aspect_ratio is custom.",
    },
  });

  for (const tier of fixture.frontend_tiers) {
    const { restored, serialized } = restoreAndSerializeLegacyValue(fixture, tier);
    expect(restored.aspect_ratio, tier.id).toBe("21:9");
    expect(serialized[1], tier.id).toBe("21:9");
  }
});


test("synthetic legacy migration rejects option reintroduction and value loss mutations", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const fixture = loadMigrationFixture();
  const tier = fixture.frontend_tiers[0];

  const optionMutation = structuredClone(fixture);
  optionMutation.selectable_aspect_ratios.splice(-1, 0, "21:9");
  expect(() => restoreAndSerializeLegacyValue(optionMutation, tier)).toThrow();

  const storedValueMutation = structuredClone(fixture);
  storedValueMutation.widget_values[1] = "16:9";
  expect(() => restoreAndSerializeLegacyValue(storedValueMutation, tier)).toThrow();

  const droppedSerialization = (state) =>
    fixture.input_ids.filter((inputId) => inputId !== "aspect_ratio").map((inputId) => state[inputId]);
  expect(() => restoreAndSerializeLegacyValue(fixture, tier, droppedSerialization)).toThrow();

  const substitutedSerialization = (state) =>
    fixture.input_ids.map((inputId) => (inputId === "aspect_ratio" ? "16:9" : state[inputId]));
  expect(() => restoreAndSerializeLegacyValue(fixture, tier, substitutedSerialization)).toThrow();
});
