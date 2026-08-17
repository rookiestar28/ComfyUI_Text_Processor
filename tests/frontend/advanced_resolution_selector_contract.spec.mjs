import { expect, test } from "@playwright/test";
import crypto from "node:crypto";
import fs from "node:fs";


const MIGRATION_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_legacy_migration_v2.json",
  import.meta.url,
);
const CURRENT_STAGE_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_current_stage_v2.json",
  import.meta.url,
);
const TARGET_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_contract_v2.json",
  import.meta.url,
);
const V3_TARGET_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_contract_v3.json",
  import.meta.url,
);
const V3_MIGRATION_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_mode_migration_v3.json",
  import.meta.url,
);
const V3_CURRENT_STAGE_FIXTURE_PATH = new URL(
  "../fixtures/advanced_resolution_selector_current_stage_v3.json",
  import.meta.url,
);


const V3_OUTPUT_MODES = ["fixed", "randomize", "randomize_all", "randomize_ratio"];
const RANDOMIZE_RATIO_POOL = ["9:7", "4:3", "19:13", "3:2", "7:4", "16:9"];
const OUTPUT_NAMES = [
  "width",
  "height",
  "resolved_aspect_ratio",
  "resolved_direction",
  "actual_megapixels",
  "pixel_error_percent",
  "aspect_error_percent",
];


const INPUTS = [
  { id: "output_mode", type: "COMBO", options: V3_OUTPUT_MODES, default: "fixed" },
  { id: "aspect_ratio", type: "COMBO", options: ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "custom"], default: "1:1" },
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


function loadV3Fixtures() {
  expect(
    fs.existsSync(V3_TARGET_FIXTURE_PATH),
    "required v3 fixture is missing: advanced_resolution_selector_contract_v3.json",
  ).toBeTruthy();
  expect(
    fs.existsSync(V3_MIGRATION_FIXTURE_PATH),
    "required v3 fixture is missing: advanced_resolution_selector_mode_migration_v3.json",
  ).toBeTruthy();
  expect(
    fs.existsSync(V3_CURRENT_STAGE_FIXTURE_PATH),
    "required v3 fixture is missing: advanced_resolution_selector_current_stage_v3.json",
  ).toBeTruthy();
  return {
    target: JSON.parse(fs.readFileSync(V3_TARGET_FIXTURE_PATH, "utf8")),
    migration: JSON.parse(fs.readFileSync(V3_MIGRATION_FIXTURE_PATH, "utf8")),
    current: JSON.parse(fs.readFileSync(V3_CURRENT_STAGE_FIXTURE_PATH, "utf8")),
  };
}


function validateV3Current(target, current) {
  expect(current).toEqual({
    schema_version: 3,
    source_boundaries: {
      canonical_presets_alias: "PUBLIC_PRESETS",
      randomize_ratio_presets_alias: "RANDOMIZE_RATIO_PRESETS",
      legacy_preset_labels: ["21:9"],
      legacy_execution_modes: ["fixed", "randomize"],
      public_preset_labels: ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9"],
      randomize_ratio_preset_labels: RANDOMIZE_RATIO_POOL,
      recognized_ratio_labels: ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9"],
      output_modes: V3_OUTPUT_MODES,
      input_order: INPUTS.map((entry) => entry.id),
      output_order: OUTPUT_NAMES,
    },
    stage: { implementation_status: "implemented", name: "current_product" },
    target_contract: {
      filename: "advanced_resolution_selector_contract_v3.json",
      sha256_hex_chunks: current.target_contract.sha256_hex_chunks,
    },
    validator_inputs: ["aspect_ratio"],
  });
  const targetSha = crypto.createHash("sha256").update(fs.readFileSync(V3_TARGET_FIXTURE_PATH)).digest("hex");
  expect(current.target_contract.sha256_hex_chunks.join("")).toBe(targetSha);
  expect(target.stage).toMatchObject({ name: "target_contract", implementation_status: "not_implemented" });
}


function validateV3Target(target) {
  expect(target.schema_version).toBe(3);
  expect(target.stage).toMatchObject({
    implementation_status: "not_implemented",
    name: "target_contract",
  });
  expect(target.inputs[0].options).toEqual(V3_OUTPUT_MODES);
  expect(target.inputs[0].tooltip).toBe(
    "Select fixed, seeded direction randomization, seeded preset and direction randomization, or seeded ratio randomization with the selected direction.",
  );
  expect(target.inputs[2].tooltip).toBe(
    "Choose the resolved orientation; randomize and randomize_all may replace it, while fixed and randomize_ratio preserve it.",
  );
  expect(target.modes.randomize_ratio).toEqual({
    direction_source: "selected",
    draw_order: ["ratio"],
    logical_draws: 1,
    ratio_pool_labels: RANDOMIZE_RATIO_POOL,
    ratio_source: "seeded_random_public_preset_excluding_1_1",
  });
  expect(target.legacy_presets[0].execution_modes).toEqual(["fixed", "randomize"]);
  expect(target.draw_cases.slice(-7).map((entry) => entry.expected[0])).toEqual([
    "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "16:9",
  ]);
  expect(target.draw_cases.slice(-7).map((entry) => entry.expected[1])).toEqual([
    "portrait", "landscape", "portrait", "landscape", "portrait", "landscape", "portrait",
  ]);
  expect(target.draw_cases.slice(-7).map((entry) => entry.selected_aspect_ratio)).toEqual([
    "1:1", "custom", "21:9", "1:1", "custom", "21:9", "1:1",
  ]);
}


function validateV3Migration(target, migration) {
  expect(Object.keys(migration)).toEqual([
    "schema_version",
    "source_contract",
    "target_contract",
    "supported_frontend_tiers",
    "input_order",
    "output_order",
    "public_output_modes",
    "legacy_recognized_ratio_labels",
    "cases",
  ]);
  expect(migration.schema_version).toBe(3);
  expect(migration.source_contract.filename).toBe(
    "advanced_resolution_selector_contract_v2.json",
  );
  expect(migration.target_contract.filename).toBe(
    "advanced_resolution_selector_contract_v3.json",
  );
  const targetSha = crypto
    .createHash("sha256")
    .update(fs.readFileSync(V3_TARGET_FIXTURE_PATH))
    .digest("hex");
  expect(migration.target_contract.sha256_hex_chunks.join("")).toBe(targetSha);
  expect(migration.supported_frontend_tiers).toEqual([
    { id: "desktop_floor", version: "1.43.18" },
    { id: "current", version: "1.49.1" },
  ]);
  expect(migration.input_order).toEqual(INPUTS.map((input) => input.id));
  expect(migration.output_order).toEqual(OUTPUT_NAMES);
  expect(migration.public_output_modes).toEqual(V3_OUTPUT_MODES);
  expect(migration.legacy_recognized_ratio_labels).toEqual(["21:9"]);
  expect(target.inputs[0].options).toEqual(migration.public_output_modes);
  expect(migration.cases.map((entry) => entry.id)).toEqual([
    "fixed_existing",
    "randomize_existing",
    "randomize_all_existing",
    "randomize_ratio_new",
  ]);
  const expectedVectors = [
    ["fixed", "16:9", "portrait", 1, 1, 1.0, 8, 0],
    ["randomize", "4:3", "landscape", 1, 1, 1.0, 8, 1],
    ["randomize_all", "custom", "portrait", 2, 1, 1.0, 8, 0],
    ["randomize_ratio", "1:1", "portrait", 1, 1, 1.0, 8, 0],
  ];
  for (const [index, contractCase] of migration.cases.entries()) {
    expect(Object.keys(contractCase)).toEqual([
      "id",
      "tiers",
      "serialized_widgets",
      "expected_restored_widgets",
      "expected_serialized_widgets",
    ]);
    expect(contractCase.tiers).toEqual(["desktop_floor", "current"]);
    expect(contractCase.serialized_widgets).toEqual(expectedVectors[index]);
    expect(contractCase.expected_restored_widgets).toEqual(expectedVectors[index]);
    expect(contractCase.expected_serialized_widgets).toEqual(expectedVectors[index]);
  }
}


test("current product stage binds the immutable seven-preset target", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  expect(
    fs.existsSync(CURRENT_STAGE_FIXTURE_PATH),
    "required v2 fixture is missing: advanced_resolution_selector_current_stage_v2.json",
  ).toBeTruthy();
  const currentStage = JSON.parse(fs.readFileSync(CURRENT_STAGE_FIXTURE_PATH, "utf8"));
  const targetBytes = fs.readFileSync(TARGET_FIXTURE_PATH);
  const targetSha = crypto.createHash("sha256").update(targetBytes).digest("hex");
  const publicOptions = INPUTS.find((input) => input.id === "aspect_ratio").options;

  expect(currentStage.stage).toEqual({
    implementation_status: "implemented",
    name: "current_product",
  });
  expect(currentStage.target_contract.filename).toBe(
    "advanced_resolution_selector_contract_v2.json",
  );
  expect(currentStage.target_contract.sha256_hex_chunks.join("")).toBe(targetSha);
  expect(currentStage.validator_inputs).toEqual(["aspect_ratio"]);
  expect(currentStage.source_boundaries.public_preset_labels).toEqual(publicOptions.slice(0, -1));
  expect(currentStage.source_boundaries.legacy_preset_labels).toEqual(["21:9"]);
  expect(publicOptions).toEqual([
    "1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "custom",
  ]);
  expect(publicOptions).not.toContain("21:9");
});


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


test("v3 target and migration freeze append-only randomize_ratio contracts", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const { target, migration, current } = loadV3Fixtures();
  validateV3Target(target);
  validateV3Migration(target, migration);
  validateV3Current(target, current);

  for (const contractCase of migration.cases) {
    expect(contractCase.tiers).toEqual(["desktop_floor", "current"]);
    const restored = Object.fromEntries(
      migration.input_order.map((inputId, index) => [
        inputId,
        contractCase.serialized_widgets[index],
      ]),
    );
    const serialized = migration.input_order.map((inputId) => restored[inputId]);
    expect(serialized, contractCase.id).toEqual(contractCase.expected_restored_widgets);
    expect(serialized, contractCase.id).toEqual(contractCase.expected_serialized_widgets);
  }

  expect(migration.cases.slice(0, 3).map((entry) => entry.serialized_widgets[0])).toEqual([
    "fixed", "randomize", "randomize_all",
  ]);
  expect(migration.cases[3].serialized_widgets[0]).toBe("randomize_ratio");
});


test("v3 browser contract rejects pool, direction, option, legacy, and serialization mutations", async ({ page }) => {
  await page.setContent("<!doctype html><html><body></body></html>");
  const fixtures = loadV3Fixtures();

  const poolMutation = structuredClone(fixtures.target);
  poolMutation.modes.randomize_ratio.ratio_pool_labels.unshift("1:1");
  expect(() => validateV3Target(poolMutation)).toThrow();

  const directionMutation = structuredClone(fixtures.target);
  directionMutation.modes.randomize_ratio.direction_source = "seeded_random";
  expect(() => validateV3Target(directionMutation)).toThrow();

  const drawMutation = structuredClone(fixtures.target);
  drawMutation.modes.randomize_ratio.draw_order.push("direction");
  expect(() => validateV3Target(drawMutation)).toThrow();

  const optionMutation = structuredClone(fixtures.migration);
  optionMutation.public_output_modes.reverse();
  expect(() => validateV3Migration(fixtures.target, optionMutation)).toThrow();

  const legacyMutation = structuredClone(fixtures.migration);
  legacyMutation.legacy_recognized_ratio_labels = [];
  expect(() => validateV3Migration(fixtures.target, legacyMutation)).toThrow();

  const serializationMutation = structuredClone(fixtures.migration);
  serializationMutation.cases[3].expected_serialized_widgets[0] = "fixed";
  expect(() => validateV3Migration(fixtures.target, serializationMutation)).toThrow();

  const currentPoolMutation = structuredClone(fixtures.current);
  currentPoolMutation.source_boundaries.randomize_ratio_preset_labels.unshift("1:1");
  expect(() => validateV3Current(fixtures.target, currentPoolMutation)).toThrow();

  const currentValidatorMutation = structuredClone(fixtures.current);
  currentValidatorMutation.validator_inputs.push("output_mode");
  expect(() => validateV3Current(fixtures.target, currentValidatorMutation)).toThrow();
});
