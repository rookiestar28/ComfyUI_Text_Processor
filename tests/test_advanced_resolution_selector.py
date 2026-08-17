import ast
import inspect
import json
import math
import random
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import advanced_resolution_selector as module
except ModuleNotFoundError:
    from .. import advanced_resolution_selector as module


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_DIR / "tests" / "fixtures" / "advanced_resolution_selector_contract_v1.json"


class DrawRecorder:
    def __init__(self, draws):
        self._draws = iter(draws)
        self.calls = []

    def __call__(self):
        self.calls.append(len(self.calls))
        try:
            return next(self._draws)
        except StopIteration as exc:
            raise AssertionError("unexpected draw") from exc


def _values(**overrides):
    values = {
        "output_mode": "fixed",
        "aspect_ratio": "1:1",
        "direction": "landscape",
        "custom_ratio_width": 1,
        "custom_ratio_height": 1,
        "megapixels": 1.0,
        "multiple": 8,
        "seed": 0,
    }
    values.update(overrides)
    return values


def _select(draw_stream=None, **overrides):
    values = _values(**overrides)
    return module._resolve_selection(
        values["output_mode"],
        values["aspect_ratio"],
        values["direction"],
        values["custom_ratio_width"],
        values["custom_ratio_height"],
        values["megapixels"],
        values["multiple"],
        values["seed"],
        draw_stream=draw_stream,
    )


class AdvancedResolutionSelectorTests(unittest.TestCase):
    def test_identity_schema_outputs_and_metadata(self):
        node = module.AdvancedResolutionSelector
        self.assertEqual("TP_AdvancedResolutionSelector", module.NODE_ID)
        self.assertEqual(
            {"TP_AdvancedResolutionSelector": node},
            module.NODE_CLASS_MAPPINGS,
        )
        self.assertEqual(
            {"TP_AdvancedResolutionSelector": "Advanced Resolution Selector"},
            module.NODE_DISPLAY_NAME_MAPPINGS,
        )
        self.assertEqual("select_resolution", node.FUNCTION)
        self.assertEqual("ComfyUI Text Processor/Image", node.CATEGORY)
        self.assertTrue(node.DESCRIPTION.strip())
        self.assertTrue(node.SEARCH_ALIASES)
        self.assertFalse(getattr(node, "OUTPUT_NODE", False))
        self.assertFalse(hasattr(node, "IS_CHANGED"))
        self.assertEqual(
            [
                "self",
                "output_mode",
                "aspect_ratio",
                "direction",
                "custom_ratio_width",
                "custom_ratio_height",
                "megapixels",
                "multiple",
                "seed",
            ],
            list(inspect.signature(node.select_resolution).parameters),
        )

        required = node.INPUT_TYPES()["required"]
        self.assertEqual(
            [
                "output_mode",
                "aspect_ratio",
                "direction",
                "custom_ratio_width",
                "custom_ratio_height",
                "megapixels",
                "multiple",
                "seed",
            ],
            list(required),
        )

        expected = {
            "output_mode": (
                ["fixed", "randomize", "randomize_all", "randomize_ratio"],
                "fixed",
                None,
                None,
                False,
                False,
                "Select fixed, seeded direction randomization, seeded preset and direction randomization, or seeded ratio randomization with the selected direction.",
            ),
            "aspect_ratio": (
                ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "custom"],
                "1:1",
                None,
                None,
                False,
                False,
                "Choose one canonical ratio or provide a positive custom ratio pair.",
            ),
            "direction": (
                ["landscape", "portrait"],
                "landscape",
                None,
                None,
                False,
                False,
                "Choose the resolved orientation; randomize and randomize_all may replace it, while fixed and randomize_ratio preserve it.",
            ),
            "custom_ratio_width": (
                None,
                1,
                1,
                10000,
                True,
                False,
                "Positive custom ratio width; used when aspect_ratio is custom.",
            ),
            "custom_ratio_height": (
                None,
                1,
                1,
                10000,
                True,
                False,
                "Positive custom ratio height; used when aspect_ratio is custom.",
            ),
            "megapixels": (
                None,
                1.0,
                0.1,
                16.0,
                False,
                False,
                "Binary 1024 squared pixel budget before multiple alignment.",
            ),
            "multiple": (
                None,
                8,
                8,
                128,
                True,
                False,
                "Align both dimensions to this positive multiple.",
            ),
            "seed": (
                None,
                0,
                0,
                4294967295,
                False,
                True,
                "Explicit uint32 seed for deterministic randomized modes.",
            ),
        }
        for name, spec in expected.items():
            with self.subTest(name=name):
                raw_type, options = required[name]
                expected_options, default, minimum, maximum, advanced, control, tooltip = spec
                if expected_options is None:
                    self.assertEqual(raw_type, "FLOAT" if name == "megapixels" else "INT")
                    self.assertNotIn("options", options)
                else:
                    self.assertEqual(expected_options, raw_type)
                self.assertEqual(default, options.get("default"))
                self.assertEqual(minimum, options.get("min"))
                self.assertEqual(maximum, options.get("max"))
                self.assertEqual(advanced, options.get("advanced", False))
                self.assertEqual(control, options.get("control_after_generate", False))
                self.assertEqual(tooltip, options.get("tooltip"))

        self.assertEqual(
            ("INT", "INT", "STRING", "STRING", "FLOAT", "FLOAT", "FLOAT"),
            node.RETURN_TYPES,
        )
        self.assertEqual(
            (
                "width",
                "height",
                "resolved_aspect_ratio",
                "resolved_direction",
                "actual_megapixels",
                "pixel_error_percent",
                "aspect_error_percent",
            ),
            node.RETURN_NAMES,
        )
        self.assertEqual(
            (
                "Aligned output width in pixels.",
                "Aligned output height in pixels.",
                "Canonical or reduced custom ratio label before direction is reported separately.",
                "Resolved landscape or portrait direction.",
                "Realized binary megapixels after multiple alignment.",
                "Signed realized pixel-area error percentage.",
                "Signed realized aspect-ratio error percentage.",
            ),
            node.OUTPUT_TOOLTIPS,
        )

    def test_fixed_uses_selected_ratio_and_direction_without_draws(self):
        for label in module.RATIO_LABELS:
            for direction in module.DIRECTIONS:
                recorder = DrawRecorder(())
                ratio, resolved_direction = _select(
                    recorder,
                    aspect_ratio=label,
                    direction=direction,
                )
                with self.subTest(label=label, direction=direction):
                    self.assertEqual(label, ratio.label)
                    self.assertEqual(direction, resolved_direction)
                    self.assertEqual([], recorder.calls)

        recorder = DrawRecorder(())
        ratio, resolved_direction = _select(
            recorder,
            aspect_ratio="custom",
            custom_ratio_width=6,
            custom_ratio_height=4,
            direction="portrait",
        )
        self.assertEqual((3, 2, "3:2"), (ratio.width, ratio.height, ratio.label))
        self.assertEqual("portrait", resolved_direction)
        self.assertEqual([], recorder.calls)

    def test_randomize_preserves_ratio_and_consumes_one_direction_draw(self):
        for selected_direction in module.DIRECTIONS:
            recorder = DrawRecorder([0.0])
            ratio, resolved_direction = _select(
                recorder,
                output_mode="randomize",
                aspect_ratio="custom",
                custom_ratio_width=6,
                custom_ratio_height=4,
                direction=selected_direction,
            )
            with self.subTest(selected_direction=selected_direction):
                self.assertEqual("3:2", ratio.label)
                self.assertEqual("landscape", resolved_direction)
                self.assertEqual([0], recorder.calls)

        recorder = DrawRecorder([0.9999999999999999])
        ratio, resolved_direction = _select(
            recorder,
            output_mode="randomize",
            aspect_ratio="9:7",
            direction="landscape",
        )
        self.assertEqual("9:7", ratio.label)
        self.assertEqual("portrait", resolved_direction)
        self.assertEqual([0], recorder.calls)

    def test_randomize_all_draws_ratio_then_direction_and_excludes_custom(self):
        for index, label in enumerate(module.RATIO_LABELS):
            recorder = DrawRecorder([(index + 0.25) / len(module.RATIO_LABELS), 0.0])
            ratio, resolved_direction = _select(
                recorder,
                output_mode="randomize_all",
                aspect_ratio="custom",
                custom_ratio_width=100,
                custom_ratio_height=50,
                direction="portrait",
            )
            with self.subTest(label=label):
                self.assertEqual(label, ratio.label)
                self.assertEqual("landscape", resolved_direction)
                self.assertEqual([0, 1], recorder.calls)

        recorder = DrawRecorder([0.9999999999999999, 0.9999999999999999])
        ratio, resolved_direction = _select(
            recorder,
            output_mode="randomize_all",
            aspect_ratio="custom",
            custom_ratio_width=10000,
            custom_ratio_height=1,
            direction="landscape",
        )
        self.assertEqual("16:9", ratio.label)
        self.assertEqual("portrait", resolved_direction)
        self.assertEqual([0, 1], recorder.calls)

    def test_randomize_ratio_uses_six_existing_presets_and_preserves_direction(self):
        expected_labels = ["9:7", "4:3", "19:13", "3:2", "7:4", "16:9"]
        self.assertEqual(expected_labels, [ratio.label for ratio in module.RANDOMIZE_RATIO_PRESETS])
        for ratio in module.RANDOMIZE_RATIO_PRESETS:
            self.assertTrue(any(ratio is public for public in module.PUBLIC_PRESETS))

        selected = ("1:1", "custom", "21:9", "1:1", "custom", "21:9")
        for index, (expected_label, selected_ratio) in enumerate(zip(expected_labels, selected, strict=True)):
            for direction in module.DIRECTIONS:
                recorder = DrawRecorder([index / len(expected_labels)])
                ratio, resolved_direction = _select(
                    recorder,
                    output_mode="randomize_ratio",
                    aspect_ratio=selected_ratio,
                    custom_ratio_width=6,
                    custom_ratio_height=4,
                    direction=direction,
                )
                with self.subTest(label=expected_label, selected=selected_ratio, direction=direction):
                    self.assertEqual(expected_label, ratio.label)
                    self.assertEqual(direction, resolved_direction)
                    self.assertEqual([0], recorder.calls)
                    self.assertNotIn(ratio.label, ("1:1", "custom", "21:9"))

        recorder = DrawRecorder([0.9999999999999999])
        ratio, direction = _select(
            recorder,
            output_mode="randomize_ratio",
            aspect_ratio="21:9",
            direction="portrait",
        )
        self.assertEqual(("16:9", "portrait"), (ratio.label, direction))
        self.assertEqual([0], recorder.calls)

    def test_randomize_ratio_seed_vectors_and_global_rng_isolation(self):
        node = module.AdvancedResolutionSelector()
        state = random.getstate()
        for seed, direction, expected in (
            (0, "portrait", ("16:9", "portrait")),
            (1, "landscape", ("9:7", "landscape")),
            (4294967295, "portrait", ("3:2", "portrait")),
        ):
            first = node.select_resolution(
                **_values(output_mode="randomize_ratio", seed=seed, direction=direction)
            )
            second = node.select_resolution(
                **_values(output_mode="randomize_ratio", seed=seed, direction=direction)
            )
            with self.subTest(seed=seed):
                self.assertEqual(expected, (first["result"][2], first["result"][3]))
                self.assertEqual(first, second)
        self.assertEqual(state, random.getstate())

    def test_validation_precedes_rng_for_all_modes_and_invalid_custom_values(self):
        cases = [
            ({"output_mode": "unknown"}, "invalid_output_mode:"),
            ({"aspect_ratio": "2:1"}, "invalid_aspect_ratio:"),
            ({"custom_ratio_width": 0}, "invalid_ratio:"),
            ({"custom_ratio_height": True}, "invalid_ratio:"),
            ({"direction": "diagonal"}, "invalid_direction:"),
            ({"megapixels": float("nan")}, "invalid_megapixels:"),
            ({"megapixels": 16.1}, "invalid_megapixels:"),
            ({"megapixels": True}, "invalid_megapixels:"),
            ({"multiple": 10}, "invalid_multiple_step:"),
            ({"multiple": True}, "invalid_multiple:"),
            ({"seed": -1}, "invalid_seed:"),
            ({"seed": 4294967296}, "invalid_seed:"),
            ({"seed": True}, "invalid_seed:"),
        ]
        for mode in ("randomize_all", "randomize_ratio"):
            for overrides, prefix in cases:
                recorder = DrawRecorder([0.0, 0.0])
                with self.subTest(mode=mode, overrides=overrides):
                    call_overrides = {"output_mode": mode, **overrides}
                    with self.assertRaisesRegex(ValueError, "^" + prefix):
                        _select(recorder, **call_overrides)
                    self.assertEqual([], recorder.calls)

    def test_legacy_21_9_executes_in_fixed_and_randomize_but_not_randomize_all(self):
        fixed_ratio, fixed_direction = _select(
            output_mode="fixed", aspect_ratio="21:9", direction="landscape"
        )
        self.assertEqual(("21:9", "landscape"), (fixed_ratio.label, fixed_direction))

        recorder = DrawRecorder([0.9999999999999999])
        random_ratio, random_direction = _select(
            recorder,
            output_mode="randomize",
            aspect_ratio="21:9",
            direction="landscape",
        )
        self.assertEqual(("21:9", "portrait"), (random_ratio.label, random_direction))
        self.assertEqual([0], recorder.calls)

        self.assertNotIn("21:9", module.RATIO_LABELS)
        self.assertNotIn("21:9", module.ASPECT_RATIO_OPTIONS)

        for aspect_ratio in ("1:1", "custom"):
            recorder = DrawRecorder([0.0, 0.0])
            with self.subTest(aspect_ratio=aspect_ratio):
                with self.assertRaisesRegex(ValueError, r"^invalid_ratio:"):
                    _select(
                        recorder,
                        output_mode="randomize_all",
                        aspect_ratio=aspect_ratio,
                        custom_ratio_width=10001,
                    )
                self.assertEqual([], recorder.calls)

    def test_invalid_draws_are_rejected_at_draw_boundary(self):
        invalid_draws = (-0.01, 1.0, float("nan"), float("inf"), True, "0")
        for value in invalid_draws:
            recorder = DrawRecorder([value])
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, r"^invalid_draw:"):
                    _select(recorder, output_mode="randomize")
                self.assertEqual([0], recorder.calls)

        recorder = DrawRecorder([0.0, 1.0])
        with self.assertRaisesRegex(ValueError, r"^invalid_draw:"):
            _select(recorder, output_mode="randomize_all")
        self.assertEqual([0, 1], recorder.calls)

    def test_seed_reproducibility_global_rng_isolation_and_f21_diagnostics(self):
        node = module.AdvancedResolutionSelector()
        values = _values(output_mode="randomize_all", seed=0)
        state = random.getstate()
        first = node.select_resolution(**values)
        second = node.select_resolution(**values)
        self.assertEqual(first, second)
        self.assertEqual(state, random.getstate())
        self.assertEqual(("7:4", "portrait"), (first["result"][2], first["result"][3]))

        max_seed = node.select_resolution(
            **_values(output_mode="randomize_all", seed=4294967295)
        )
        self.assertEqual(
            ("3:2", "landscape"),
            (max_seed["result"][2], max_seed["result"][3]),
        )
        self.assertNotEqual(first, max_seed)

        expected = module.plan_resolution(
            module.ResolutionRequest(
                module.normalize_ratio(6, 4),
                "portrait",
                1.0,
                8,
            )
        )
        with patch.object(module, "plan_resolution", wraps=module.plan_resolution) as planner:
            actual = node.select_resolution(
                **_values(
                    aspect_ratio="custom",
                    custom_ratio_width=6,
                    custom_ratio_height=4,
                    direction="portrait",
                )
            )
        planner.assert_called_once()
        request = planner.call_args.args[0]
        self.assertIsInstance(request, module.ResolutionRequest)
        self.assertEqual(
            (
                expected.width,
                expected.height,
                expected.resolved_aspect_ratio,
                expected.resolved_direction,
                expected.actual_megapixels,
                expected.pixel_error_percent,
                expected.aspect_error_percent,
            ),
            actual["result"],
        )
        self.assertEqual(8, request.multiple)

    def test_success_returns_namespaced_ui_and_unchanged_result_tuple(self):
        node = module.AdvancedResolutionSelector()
        output = node.select_resolution(**_values())

        self.assertEqual({"ui", "result"}, set(output))
        self.assertIsInstance(output["result"], tuple)
        self.assertEqual(7, len(output["result"]))
        self.assertEqual(
            {
                "tp_advanced_resolution": [
                    {
                        "width": output["result"][0],
                        "height": output["result"][1],
                    }
                ]
            },
            output["ui"],
        )
        self.assertGreater(output["ui"]["tp_advanced_resolution"][0]["width"], 0)
        self.assertGreater(output["ui"]["tp_advanced_resolution"][0]["height"], 0)

    def test_invalid_execution_emits_no_partial_ui_payload(self):
        node = module.AdvancedResolutionSelector()
        with self.assertRaisesRegex(ValueError, r"^invalid_direction:"):
            node.select_resolution(**_values(direction="diagonal"))

    def test_adapter_matches_all_frozen_numerical_oracles(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        node = module.AdvancedResolutionSelector()
        for case in fixture["numerical_cases"]:
            ratio_width, ratio_height = case["ratio"]
            label = next(
                (
                    preset["label"]
                    for preset in fixture["presets"]
                    if preset["pair"] == case["ratio"]
                ),
                "custom",
            )
            values = _values(
                aspect_ratio=label,
                custom_ratio_width=ratio_width,
                custom_ratio_height=ratio_height,
                direction=case["direction"],
                megapixels=case["megapixels"],
                multiple=case["multiple"],
            )
            actual = node.select_resolution(**values)
            result = actual["result"]
            expected = case["expected"]
            with self.subTest(case=case["name"]):
                self.assertEqual((expected["width"], expected["height"]), result[:2])
                self.assertEqual(expected["resolved_aspect_ratio"], result[2])
                self.assertEqual(case["direction"], result[3])
                self.assertTrue(
                    math.isclose(
                        expected["actual_megapixels"],
                        result[4],
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        expected["pixel_error_percent"],
                        result[5],
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        expected["aspect_error_percent"],
                        result[6],
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                )

    def test_adapter_source_has_no_global_rng_or_untrusted_boundary(self):
        source_path = REPO_DIR / "advanced_resolution_selector.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(
            imports <= {"__future__", "math", "random", "typing", "advanced_resolution_selector_core"},
            imports,
        )
        self.assertNotIn("random.choice", source)
        self.assertNotIn("random.random(", source)
        self.assertNotIn("secrets", source)
        self.assertNotIn("IS_CHANGED", source)
        self.assertNotIn("open(", source)
        self.assertNotIn("requests", source)


if __name__ == "__main__":
    unittest.main()
