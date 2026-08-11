import ast
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

try:
    from advanced_resolution_selector_core import (
        CANONICAL_PRESETS,
        DIRECTIONS,
        MAX_DIMENSION,
        SCORE_ORDER,
        AspectRatio,
        ResolutionRequest,
        canonical_ratio,
        normalize_ratio,
        plan_resolution,
        _select_best_candidate,
    )
except ModuleNotFoundError:
    from ..advanced_resolution_selector_core import (
        CANONICAL_PRESETS,
        DIRECTIONS,
        MAX_DIMENSION,
        AspectRatio,
        ResolutionRequest,
        canonical_ratio,
        normalize_ratio,
        plan_resolution,
        _select_best_candidate,
    )


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_DIR / "tests" / "fixtures" / "advanced_resolution_selector_contract_v1.json"
CORE_PATH = REPO_DIR / "advanced_resolution_selector_core.py"
PIXEL_UNIT = 1024 * 1024
CORE_MODULE = importlib.import_module("advanced_resolution_selector_core")


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _expected_ratio(case, fixture):
    preset_labels = {tuple(entry["pair"]): entry["label"] for entry in fixture["presets"]}
    return normalize_ratio(*case["ratio"], label=preset_labels.get(tuple(case["ratio"])))


def _native_score(case, width, height):
    target = case["megapixels"] * 1024 * 1024
    ratio_pair = case["ratio"]
    ratio = ratio_pair[0] / ratio_pair[1]
    if case["direction"] == "portrait":
        ratio = 1 / ratio
    pixel_error = (width * height / target - 1) * 100
    aspect_error = ((width / height) / ratio - 1) * 100
    return max(abs(pixel_error), abs(aspect_error)), abs(pixel_error) + abs(aspect_error)


def _run_source_mutation(replacement, runner):
    source = CORE_PATH.read_text(encoding="utf-8")
    before, after = replacement
    if source.count(before) != 1:
        raise AssertionError("mutation anchor must occur exactly once")
    with tempfile.TemporaryDirectory(prefix="resolution_core_mutation_") as temp_dir:
        temp_path = Path(temp_dir) / "advanced_resolution_selector_core.py"
        temp_path.write_text(source.replace(before, after), encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = temp_dir
        return subprocess.run(
            [sys.executable, "-c", runner],
            cwd=temp_dir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )


class AdvancedResolutionSelectorCoreTests(unittest.TestCase):
    def test_core_is_standard_library_only_and_unregistered(self):
        source = (REPO_DIR / "advanced_resolution_selector_core.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"__future__", "dataclasses", "math", "typing"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= allowed, imported)
        self.assertNotIn("random", source.lower())
        self.assertNotIn("advanced_resolution_selector_core", (REPO_DIR / "__init__.py").read_text(encoding="utf-8"))
        module = importlib.import_module("advanced_resolution_selector_core")
        self.assertEqual("advanced_resolution_selector_core", module.__name__)

    def test_immutable_typed_boundaries(self):
        ratio = normalize_ratio(6, 4)
        request = ResolutionRequest(ratio, "landscape", 1.0, 8)
        result = plan_resolution(request)
        self.assertIsInstance(ratio, AspectRatio)
        with self.assertRaises(FrozenInstanceError):
            ratio.width = 4
        with self.assertRaises(FrozenInstanceError):
            request.megapixels = 2.0
        with self.assertRaises(FrozenInstanceError):
            result.width = 1
        with self.assertRaisesRegex(ValueError, "^invalid_ratio:"):
            AspectRatio(1, 1, "21:9")
        alias = AspectRatio(7, 3, "21:9")
        self.assertEqual((7, 3, "21:9"), (alias.width, alias.height, alias.label))

    def test_canonical_and_custom_labels_are_stable(self):
        self.assertEqual([ratio.label for ratio in CANONICAL_PRESETS], [
            "1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9"
        ])
        self.assertEqual(DIRECTIONS, ("landscape", "portrait"))
        canonical = canonical_ratio("21:9")
        self.assertEqual((7, 3), (canonical.width, canonical.height))
        self.assertEqual("21:9", canonical.label)
        custom = normalize_ratio(100, 50)
        self.assertEqual((2, 1), (custom.width, custom.height))
        self.assertEqual("2:1", custom.label)

    def test_complete_preset_direction_and_boundary_matrix(self):
        for ratio in CANONICAL_PRESETS:
            for direction in DIRECTIONS:
                with self.subTest(label=ratio.label, direction=direction):
                    result = plan_resolution(ResolutionRequest(ratio, direction, 1.0, 8))
                    self.assertGreaterEqual(result.width, 1)
                    self.assertGreaterEqual(result.height, 1)
                    self.assertEqual(0, result.width % 8)
                    self.assertEqual(0, result.height % 8)
                    self.assertLessEqual(max(result.width, result.height), MAX_DIMENSION)
                    self.assertEqual(ratio.label, result.resolved_aspect_ratio)

        custom = normalize_ratio(6, 4)
        for direction in DIRECTIONS:
            result = plan_resolution(ResolutionRequest(custom, direction, 1.0, 8))
            self.assertEqual("3:2", result.resolved_aspect_ratio)
            self.assertEqual(direction, result.resolved_direction)

        for megapixels in (0.1, 1.0, 16.0):
            for multiple in range(8, 129, 4):
                with self.subTest(megapixels=megapixels, multiple=multiple):
                    result = plan_resolution(
                        ResolutionRequest(canonical_ratio("1:1"), "landscape", megapixels, multiple)
                    )
                    self.assertEqual(0, result.width % multiple)
                    self.assertEqual(0, result.height % multiple)
                    self.assertLessEqual(max(result.width, result.height), MAX_DIMENSION)

        maximum_ideal = math.sqrt(16.0 * 1024 * 1024 * 10000)
        bound_by_multiple = {
            multiple: multiple * (round(maximum_ideal / multiple) + 1)
            for multiple in range(8, 129, 4)
        }
        self.assertEqual(409752, max(bound_by_multiple.values()))
        self.assertEqual(108, max(bound_by_multiple, key=bound_by_multiple.get))

    def test_core_matches_every_t08_numerical_oracle(self):
        fixture = _load_fixture()
        for case in fixture["numerical_cases"]:
            with self.subTest(case=case["name"]):
                result = plan_resolution(
                    ResolutionRequest(
                        _expected_ratio(case, fixture),
                        case["direction"],
                        case["megapixels"],
                        case["multiple"],
                    )
                )
                expected = case["expected"]
                self.assertEqual((expected["width"], expected["height"]), (result.width, result.height))
                self.assertEqual(expected["resolved_aspect_ratio"], result.resolved_aspect_ratio)
                self.assertEqual(case["direction"], result.resolved_direction)
                self.assertTrue(math.isclose(expected["actual_megapixels"], result.actual_megapixels, rel_tol=1e-12, abs_tol=1e-12))
                self.assertTrue(math.isclose(expected["pixel_error_percent"], result.pixel_error_percent, rel_tol=1e-12, abs_tol=1e-12))
                self.assertTrue(math.isclose(expected["aspect_error_percent"], result.aspect_error_percent, rel_tol=1e-12, abs_tol=1e-12))
                self.assertTrue(math.isfinite(result.realized_aspect_ratio))
                self.assertLessEqual(max(result.width, result.height), MAX_DIMENSION)

    def test_halfway_candidates_and_joint_objective(self):
        from advanced_resolution_selector_core import _axis_candidates

        self.assertEqual((1, 2, 3), _axis_candidates(2.5 * 8, 8))
        self.assertEqual((3, 4, 5), _axis_candidates(3.5 * 8, 8))
        fixture = _load_fixture()
        coarse = next(case for case in fixture["numerical_cases"] if case["name"] == "extreme_custom")
        ratio = _expected_ratio(coarse, fixture)
        result = plan_resolution(ResolutionRequest(ratio, coarse["direction"], coarse["megapixels"], coarse["multiple"]))
        target = coarse["megapixels"] * 1024 * 1024
        oriented_ratio = ratio.width / ratio.height
        native_width = max(1, round(math.sqrt(target * oriented_ratio) / coarse["multiple"])) * coarse["multiple"]
        native_height = max(1, round(math.sqrt(target / oriented_ratio) / coarse["multiple"])) * coarse["multiple"]
        self.assertNotEqual((result.width, result.height), (native_width, native_height))
        self.assertLessEqual(
            _native_score(coarse, result.width, result.height),
            _native_score(coarse, native_width, native_height),
        )
        self.assertEqual(
            (
                "max_abs_error",
                "sum_abs_error",
                "abs_pixel_error",
                "abs_aspect_error",
                "native_manhattan_distance",
                "width",
                "height",
            ),
            SCORE_ORDER,
        )

    def test_validation_errors_are_stable_and_content_safe(self):
        cases = [
            (("ratio", (0, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("ratio", (True, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("ratio", (-1, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("ratio", (10001, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("ratio", (1.0, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("direction", "diagonal"), "invalid_direction: direction must be landscape or portrait"),
            (("direction", None), "invalid_direction: direction must be landscape or portrait"),
            (("megapixels", float("nan")), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("megapixels", float("inf")), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("megapixels", 0.0), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("megapixels", 16.1), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("megapixels", True), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("multiple", 7), "invalid_multiple: integer value in 8..128 is required"),
            (("multiple", 130), "invalid_multiple: integer value in 8..128 is required"),
            (("multiple", 8.5), "invalid_multiple: integer value in 8..128 is required"),
            (("multiple", 10), "invalid_multiple_step: multiple must equal 8 + 4*n"),
            (("multiple", True), "invalid_multiple: integer value in 8..128 is required"),
        ]
        ratio = normalize_ratio(1, 1)
        for (field, value), message in cases:
            with self.subTest(field=field, value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "^" + re_escape(message) + "$"):
                    if field == "ratio":
                        normalize_ratio(*value)
                    else:
                        ResolutionRequest(ratio, "landscape" if field != "direction" else value, 1.0 if field != "megapixels" else value, 8 if field != "multiple" else value)

    def test_score_order_sign_and_candidate_mutation_guards(self):
        fixture = _load_fixture()
        coarse = next(case for case in fixture["numerical_cases"] if case["name"] == "coarse_wide")
        ratio = _expected_ratio(coarse, fixture)
        result = plan_resolution(ResolutionRequest(ratio, coarse["direction"], coarse["megapixels"], coarse["multiple"]))
        self.assertLess(result.pixel_error_percent, 0)
        self.assertGreater(result.aspect_error_percent, 0)
        from advanced_resolution_selector_core import _axis_candidates

        candidates = _axis_candidates(409600.0, 128)
        self.assertEqual(tuple(sorted(candidates)), candidates)
        self.assertEqual(candidates, tuple(sorted(reversed(candidates))))
        altered_score_order = list(SCORE_ORDER)
        altered_score_order[0], altered_score_order[1] = altered_score_order[1], altered_score_order[0]
        self.assertNotEqual(tuple(altered_score_order), SCORE_ORDER)
        altered_expected = dict(coarse["expected"])
        altered_expected["pixel_error_percent"] *= -1
        self.assertNotEqual(altered_expected["pixel_error_percent"], result.pixel_error_percent)

    def test_score_fields_are_isolated_and_candidate_order_is_stable(self):
        base = (10.0, 20.0, 30.0, 40.0, 50, 60, 70)
        for field_index in range(len(base)):
            lower = list(base)
            higher = list(base)
            lower[field_index] -= 1
            higher[field_index] += 1
            with self.subTest(field_index=field_index):
                selected = _select_best_candidate(
                    ((0, 0), (1, 1)),
                    lambda width, _height: tuple(lower if width == 0 else higher),
                )
                self.assertEqual((0, 0), selected)

        tied_prefix = (1.0, 2.0, 3.0, 4.0, 5)
        scores = {
            (2, 3): tied_prefix + (2, 8),
            (1, 4): tied_prefix + (1, 4),
            (1, 5): tied_prefix + (1, 5),
        }
        for candidates in (tuple(scores), tuple(reversed(tuple(scores)))):
            with self.subTest(candidates=candidates):
                self.assertEqual(
                    (1, 4),
                    _select_best_candidate(candidates, lambda width, height: scores[(width, height)]),
                )

        request = ResolutionRequest(canonical_ratio("1:1"), "landscape", 0.1, 24)
        original = plan_resolution(request)
        width_candidates = CORE_MODULE._axis_candidates(323.404, 24)
        height_candidates = CORE_MODULE._axis_candidates(323.404, 24)
        with patch.object(
            CORE_MODULE,
            "_axis_candidates",
            side_effect=[tuple(reversed(width_candidates)), tuple(reversed(height_candidates))],
        ):
            permuted = CORE_MODULE.plan_resolution(request)
        self.assertEqual((original.width, original.height), (permuted.width, permuted.height))

    def test_executable_source_mutations_fail_contract_predicates(self):
        score_mutation = (
            "        max(abs(pixel_error), abs(aspect_error)),\n"
            "        abs(pixel_error) + abs(aspect_error),",
            "        abs(pixel_error) + abs(aspect_error),\n"
            "        max(abs(pixel_error), abs(aspect_error)),",
        )
        score_run = _run_source_mutation(
            score_mutation,
            """
from advanced_resolution_selector_core import ResolutionRequest, canonical_ratio, plan_resolution
result = plan_resolution(ResolutionRequest(canonical_ratio('1:1'), 'landscape', 0.1, 24))
assert (result.width, result.height) == (312, 336), (result.width, result.height)
""",
        )
        self.assertNotEqual(score_run.returncode, 0, score_run.stdout + score_run.stderr)

        sign_mutation = (
            "    pixel_error_percent = (width * height / target_pixels - 1) * 100",
            "    pixel_error_percent = (1 - width * height / target_pixels) * 100",
        )
        sign_run = _run_source_mutation(
            sign_mutation,
            """
from advanced_resolution_selector_core import ResolutionRequest, canonical_ratio, plan_resolution
result = plan_resolution(ResolutionRequest(canonical_ratio('1:1'), 'landscape', 0.1, 8))
assert result.pixel_error_percent < 0, result.pixel_error_percent
""",
        )
        self.assertNotEqual(sign_run.returncode, 0, sign_run.stdout + sign_run.stderr)

    def test_complete_invalid_matrix_and_diagnostic_self_consistency(self):
        invalid_ratios = (
            (0, 1), (1, 0), (-1, 1), (1, -1), (10001, 1), (1, 10001),
            (1.0, 1), (1, 1.0), ("1", 1), (1, "1"), (None, 1), (1, None),
            (True, 1), (1, False),
        )
        for width, height in invalid_ratios:
            with self.subTest(field="ratio", value=(width, height)):
                with self.assertRaisesRegex(ValueError, "^invalid_ratio:"):
                    normalize_ratio(width, height)

        ratio = normalize_ratio(1, 1)
        invalid_directions = (None, "", "diagonal", 1, True, b"landscape", [])
        for direction in invalid_directions:
            with self.subTest(field="direction", value=repr(direction)):
                with self.assertRaisesRegex(ValueError, "^invalid_direction:"):
                    ResolutionRequest(ratio, direction, 1.0, 8)

        invalid_megapixels = (
            None, "1.0", complex(1, 0), True, float("nan"), float("inf"),
            float("-inf"), -0.1, 0.0, 16.0001,
        )
        for megapixels in invalid_megapixels:
            with self.subTest(field="megapixels", value=repr(megapixels)):
                with self.assertRaisesRegex(ValueError, "^invalid_megapixels:"):
                    ResolutionRequest(ratio, "landscape", megapixels, 8)

        invalid_multiples = (None, "8", 8.0, True, 7, 129, 130, 9, 10, 127)
        for multiple in invalid_multiples:
            with self.subTest(field="multiple", value=repr(multiple)):
                expected = "^invalid_multiple_step:" if multiple in (9, 10, 127) else "^invalid_multiple:"
                with self.assertRaisesRegex(ValueError, expected):
                    ResolutionRequest(ratio, "landscape", 1.0, multiple)

        request = ResolutionRequest(ratio, "landscape", 1.0, 8)
        with patch.object(CORE_MODULE.math, "sqrt", return_value=float("inf")):
            with self.assertRaisesRegex(ValueError, "^invalid_numeric:"):
                CORE_MODULE.plan_resolution(request)

        matrix_ratios = tuple(CANONICAL_PRESETS) + (normalize_ratio(6, 4), normalize_ratio(10000, 1))
        saw_pixel_signs = set()
        saw_aspect_signs = set()
        for selected_ratio in matrix_ratios:
            for direction in DIRECTIONS:
                oriented_ratio = selected_ratio.width / selected_ratio.height
                if direction == "portrait":
                    oriented_ratio = 1 / oriented_ratio
                for megapixels in (0.1, 1.0, 16.0):
                    for multiple in range(8, 129, 4):
                        with self.subTest(
                            ratio=selected_ratio.label,
                            direction=direction,
                            megapixels=megapixels,
                            multiple=multiple,
                        ):
                            result = plan_resolution(
                                ResolutionRequest(selected_ratio, direction, megapixels, multiple)
                            )
                            target_pixels = megapixels * PIXEL_UNIT
                            expected_actual = result.width * result.height / PIXEL_UNIT
                            expected_realized = result.width / result.height
                            expected_pixel_error = (result.width * result.height / target_pixels - 1) * 100
                            expected_aspect_error = (expected_realized / oriented_ratio - 1) * 100
                            self.assertGreater(result.width, 0)
                            self.assertGreater(result.height, 0)
                            self.assertEqual(0, result.width % multiple)
                            self.assertEqual(0, result.height % multiple)
                            self.assertTrue(math.isfinite(result.actual_megapixels))
                            self.assertTrue(math.isfinite(result.realized_aspect_ratio))
                            self.assertTrue(math.isfinite(result.pixel_error_percent))
                            self.assertTrue(math.isfinite(result.aspect_error_percent))
                            self.assertAlmostEqual(expected_actual, result.actual_megapixels, places=12)
                            self.assertAlmostEqual(expected_realized, result.realized_aspect_ratio, places=12)
                            self.assertAlmostEqual(expected_pixel_error, result.pixel_error_percent, places=12)
                            self.assertAlmostEqual(expected_aspect_error, result.aspect_error_percent, places=12)
                            saw_pixel_signs.add(0 if result.pixel_error_percent == 0 else int(math.copysign(1, result.pixel_error_percent)))
                            saw_aspect_signs.add(0 if result.aspect_error_percent == 0 else int(math.copysign(1, result.aspect_error_percent)))
        self.assertTrue({-1, 1}.issubset(saw_pixel_signs))
        self.assertTrue({-1, 1}.issubset(saw_aspect_signs))

    def test_multiple_congruence_and_dimension_safety(self):
        ratio = normalize_ratio(10000, 1)
        for multiple in (8, 12, 128):
            result = plan_resolution(ResolutionRequest(ratio, "landscape", 16.0, multiple))
            self.assertEqual(0, result.width % multiple)
            self.assertEqual(0, result.height % multiple)
            self.assertLessEqual(max(result.width, result.height), MAX_DIMENSION)


def re_escape(value):
    import re

    return re.escape(value)


if __name__ == "__main__":
    unittest.main()
