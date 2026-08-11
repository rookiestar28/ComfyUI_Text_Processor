import ast
import importlib
import json
import math
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

try:
    from advanced_resolution_selector_core import (
        CANONICAL_PRESETS,
        DIRECTIONS,
        MAX_DIMENSION,
        AspectRatio,
        ResolutionRequest,
        canonical_ratio,
        normalize_ratio,
        plan_resolution,
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
    )


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_DIR / "tests" / "fixtures" / "advanced_resolution_selector_contract_v1.json"


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

    def test_validation_errors_are_stable_and_content_safe(self):
        cases = [
            (("ratio", (0, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("ratio", (True, 1)), "invalid_ratio: positive integer ratio components in 1..10000 are required"),
            (("direction", "diagonal"), "invalid_direction: direction must be landscape or portrait"),
            (("megapixels", float("nan")), "invalid_megapixels: finite value in 0.1..16.0 is required"),
            (("megapixels", 16.1), "invalid_megapixels: finite value in 0.1..16.0 is required"),
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
