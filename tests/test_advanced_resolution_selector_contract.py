import copy
import json
import math
import random
import re
import unittest
from fractions import Fraction
from pathlib import Path

try:
    from test_host_compatibility_contracts import PackageImportContext
except ModuleNotFoundError:
    from tests.test_host_compatibility_contracts import PackageImportContext


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_DIR / "tests" / "fixtures" / "advanced_resolution_selector_contract_v1.json"
FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference[/\\]|ROADMAP\.md|"
    r"command[ _-]?log|implementation[ _-]?record|api[_ -]?key|authorization:|"
    r"cookie:|private[ _-]?key|prompt|workflow)"
)


def _load_fixture(test_case):
    test_case.assertTrue(FIXTURE_PATH.is_file(), "T08 contract fixture is required")
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        fixture = json.load(handle)
    test_case.assertEqual(1, fixture.get("schema_version"))
    return fixture


def _ratio_from_pair(pair):
    width, height = pair
    divisor = math.gcd(width, height)
    return width // divisor, height // divisor


def _oriented_ratio(pair, direction):
    width, height = pair
    return width / height if direction == "landscape" else height / width


def _oracle_dimensions(case):
    target_pixels = case["megapixels"] * 1024 * 1024
    ratio = _oriented_ratio(case["ratio"], case["direction"])
    multiple = case["multiple"]
    ideal_width = math.sqrt(target_pixels * ratio)
    ideal_height = math.sqrt(target_pixels / ratio)

    def candidates(ideal):
        index = ideal / multiple
        rounded = round(index)
        return sorted(
            {
                candidate
                for candidate in (
                    rounded,
                    math.floor(index),
                    math.ceil(index),
                    rounded - 1,
                    rounded + 1,
                )
                if candidate >= 1
            }
        )

    width_index = ideal_width / multiple
    height_index = ideal_height / multiple
    native_width = max(1, round(width_index))
    native_height = max(1, round(height_index))
    best = None
    for width_index_candidate in candidates(ideal_width):
        for height_index_candidate in candidates(ideal_height):
            width = width_index_candidate * multiple
            height = height_index_candidate * multiple
            actual_pixels = width * height
            pixel_error = (actual_pixels / target_pixels - 1) * 100
            aspect_error = ((width / height) / ratio - 1) * 100
            score = (
                max(abs(pixel_error), abs(aspect_error)),
                abs(pixel_error) + abs(aspect_error),
                abs(pixel_error),
                abs(aspect_error),
                abs(width_index_candidate - native_width)
                + abs(height_index_candidate - native_height),
                width,
                height,
            )
            candidate = (score, width, height, pixel_error, aspect_error)
            if best is None or candidate[0] < best[0]:
                best = candidate
    return best


def _validate_fixture_contract(fixture):
    """Run the contract assertions against an arbitrary fixture copy.

    The positive tests below keep each contract area readable. This compact
    validator is intentionally duplicated at the mutation boundary so the
    suite proves that declared drift is rejected rather than merely accepted
    for the one pristine fixture on disk.
    """

    def expect(actual, expected, field):
        if actual != expected:
            raise AssertionError(f"{field} drifted")

    expect(
        fixture["node"],
        {
            "id": "TP_AdvancedResolutionSelector",
            "display_name": "Advanced Resolution Selector",
            "category": "ComfyUI Text Processor/Image",
            "function": "select_resolution",
            "api": "v1",
            "classification": "stateless",
        },
        "node",
    )
    expect(
        fixture["stage"],
        {
            "name": "T08_unregistered",
            "expected_node_count": 18,
            "expected_visible_input_count": 145,
            "expected_rich_help_count": 9,
            "forbidden_registered_id": "TP_AdvancedResolutionSelector",
        },
        "stage",
    )

    expected_labels = ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9"]
    expected_pairs = [[1, 1], [9, 7], [4, 3], [19, 13], [3, 2], [7, 4], [16, 9], [21, 9]]
    expect([entry["label"] for entry in fixture["presets"]], expected_labels, "preset order")
    expect([entry["pair"] for entry in fixture["presets"]], expected_pairs, "preset pairs")
    if len({tuple(entry["pair"]) for entry in fixture["presets"]}) != len(expected_pairs):
        raise AssertionError("preset uniqueness drifted")
    if not all(entry["pair"][0] >= entry["pair"][1] for entry in fixture["presets"]):
        raise AssertionError("preset orientation drifted")
    expect(fixture["directions"], ["landscape", "portrait"], "direction order")
    expect(fixture["custom_ratio"]["sentinel"], "custom", "custom sentinel")
    expect(fixture["custom_ratio"]["randomize_all_excluded"], True, "custom exclusion")

    expect(
        fixture["modes"],
        {
            "fixed": {
                "ratio_source": "selected",
                "direction_source": "selected",
                "logical_draws": 0,
                "draw_order": [],
            },
            "randomize": {
                "ratio_source": "selected",
                "direction_source": "seeded_random",
                "logical_draws": 1,
                "draw_order": ["direction"],
            },
            "randomize_all": {
                "ratio_source": "seeded_random_preset",
                "direction_source": "seeded_random",
                "logical_draws": 2,
                "draw_order": ["ratio", "direction"],
            },
        },
        "mode draw contract",
    )

    pools = {"ratio": expected_labels, "direction": ["landscape", "portrait"]}
    for case in fixture["draw_cases"]:
        draws = case["draws"]
        if not all(0.0 <= draw < 1.0 for draw in draws):
            raise AssertionError("draw domain drifted")
        resolved = [
            pools[pool_name][int(draw * len(pools[pool_name]))]
            for draw, pool_name in zip(draws, case["draw_order"], strict=True)
        ]
        expect(resolved, case["expected"], f"draw case {case['mode']}")
        expect(len(draws), case["logical_draws"], f"draw count {case['mode']}")

    expect(
        [entry["name"] for entry in fixture["inputs"]],
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
        "input order",
    )
    expect(
        [entry["name"] for entry in fixture["outputs"]],
        [
            "width",
            "height",
            "resolved_aspect_ratio",
            "resolved_direction",
            "actual_megapixels",
            "pixel_error_percent",
            "aspect_error_percent",
        ],
        "output order",
    )
    expect(
        [entry["type"] for entry in fixture["outputs"]],
        ["INT", "INT", "STRING", "STRING", "FLOAT", "FLOAT", "FLOAT"],
        "output types",
    )
    expect(
        [entry["default"] for entry in fixture["inputs"]],
        ["fixed", "1:1", "landscape", 1, 1, 1.0, 8, 0],
        "input defaults",
    )
    expect(fixture["inputs"][-1]["control_after_generate"], True, "seed control")
    expect(fixture["inputs"][3]["advanced"], True, "custom width advanced flag")
    expect(fixture["inputs"][4]["advanced"], True, "custom height advanced flag")
    expect(fixture["inputs"][6]["advanced"], True, "multiple advanced flag")

    expected_inputs = [
        {
            "name": "output_mode",
            "type": "COMBO",
            "default": "fixed",
            "options": ["fixed", "randomize", "randomize_all"],
            "step": None,
            "bounds": None,
            "advanced": False,
            "control_after_generate": False,
            "tooltip": "Select fixed, seeded direction randomization, or seeded preset and direction randomization.",
        },
        {
            "name": "aspect_ratio",
            "type": "COMBO",
            "default": "1:1",
            "options": ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9", "custom"],
            "step": None,
            "bounds": None,
            "advanced": False,
            "control_after_generate": False,
            "tooltip": "Choose one canonical ratio or provide a positive custom ratio pair.",
        },
        {
            "name": "direction",
            "type": "COMBO",
            "default": "landscape",
            "options": ["landscape", "portrait"],
            "step": None,
            "bounds": None,
            "advanced": False,
            "control_after_generate": False,
            "tooltip": "Choose the resolved orientation; randomized modes may replace it with a seeded draw.",
        },
        {
            "name": "custom_ratio_width",
            "type": "INT",
            "default": 1,
            "options": None,
            "step": 1,
            "bounds": [1, 10000],
            "advanced": True,
            "control_after_generate": False,
            "tooltip": "Positive custom ratio width; used when aspect_ratio is custom.",
        },
        {
            "name": "custom_ratio_height",
            "type": "INT",
            "default": 1,
            "options": None,
            "step": 1,
            "bounds": [1, 10000],
            "advanced": True,
            "control_after_generate": False,
            "tooltip": "Positive custom ratio height; used when aspect_ratio is custom.",
        },
        {
            "name": "megapixels",
            "type": "FLOAT",
            "default": 1.0,
            "options": None,
            "step": 0.1,
            "bounds": [0.1, 16.0],
            "advanced": False,
            "control_after_generate": False,
            "tooltip": "Binary 1024 squared pixel budget before multiple alignment.",
        },
        {
            "name": "multiple",
            "type": "INT",
            "default": 8,
            "options": None,
            "step": 4,
            "bounds": [8, 128],
            "advanced": True,
            "control_after_generate": False,
            "tooltip": "Align both dimensions to this positive multiple.",
        },
        {
            "name": "seed",
            "type": "INT",
            "default": 0,
            "options": None,
            "step": 1,
            "bounds": [0, 4294967295],
            "advanced": False,
            "control_after_generate": True,
            "tooltip": "Explicit uint32 seed for deterministic randomized modes.",
        },
    ]
    for index, expected in enumerate(expected_inputs):
        actual = fixture["inputs"][index]
        for field, expected_value in expected.items():
            default = False if field in {"advanced", "control_after_generate"} else None
            expect(actual.get(field, default), expected_value, f"input {index} {field}")

    expected_outputs = [
        ("width", "INT", "Aligned output width in pixels."),
        ("height", "INT", "Aligned output height in pixels."),
        (
            "resolved_aspect_ratio",
            "STRING",
            "Canonical or reduced custom ratio label before direction is reported separately.",
        ),
        ("resolved_direction", "STRING", "Resolved landscape or portrait direction."),
        ("actual_megapixels", "FLOAT", "Realized binary megapixels after multiple alignment."),
        ("pixel_error_percent", "FLOAT", "Signed realized pixel-area error percentage."),
        ("aspect_error_percent", "FLOAT", "Signed realized aspect-ratio error percentage."),
    ]
    for index, (name, output_type, tooltip) in enumerate(expected_outputs):
        actual = fixture["outputs"][index]
        expect(actual.get("name"), name, f"output {index} name")
        expect(actual.get("type"), output_type, f"output {index} type")
        expect(actual.get("tooltip"), tooltip, f"output {index} tooltip")

    expect(
        fixture["validation"],
        {
            "error_type": "ValueError",
            "failure_policy": "reject_before_arithmetic",
            "safe_error_ids": [
                "invalid_direction",
                "invalid_megapixels",
                "invalid_multiple",
                "invalid_ratio",
            ],
        },
        "validation policy",
    )
    expect(
        fixture["invalid_inputs"],
        [
            {"error_id": "invalid_ratio", "field": "ratio", "value": [0, 1]},
            {"error_id": "invalid_ratio", "field": "ratio", "value": [True, 1]},
            {"error_id": "invalid_direction", "field": "direction", "value": "diagonal"},
            {"error_id": "invalid_megapixels", "field": "megapixels", "value": 0.0},
            {"error_id": "invalid_megapixels", "field": "megapixels", "value": 16.1},
            {"error_id": "invalid_megapixels", "field": "megapixels", "value_kind": "non_finite_nan"},
            {"error_id": "invalid_multiple", "field": "multiple", "value": 6},
            {"error_id": "invalid_multiple", "field": "multiple", "value": 8.5},
        ],
        "invalid input cases",
    )

    expect(
        fixture["provenance"],
        [
            {
                "commit": "9cf9133",
                "name": "ComfyUI native ResolutionSelector source",
                "url": "https://github.com/Comfy-Org/ComfyUI/blob/9cf9133/comfy_extras/nodes_resolution.py",
            },
            {
                "commit": "9780746",
                "name": "WLSH SDXL resolution reference",
                "url": "https://github.com/wallish77/wlsh_nodes/blob/9780746/wlsh_nodes.py",
            },
        ],
        "provenance",
    )

    expected_seed_cases = fixture["seed_cases"]
    for case in expected_seed_cases:
        rng = random.Random(case["seed"])
        draw_count = 1 if case["mode"] == "randomize" else 2
        draws = [rng.random() for _ in range(draw_count)]
        for expected_draw, actual_draw in zip(case["draws"], draws, strict=True):
            if expected_draw != actual_draw:
                raise AssertionError(f"seed draw {case['seed']} drifted")
        order = ["direction"] if case["mode"] == "randomize" else ["ratio", "direction"]
        resolved = [
            pools[pool_name][int(draw * len(pools[pool_name]))]
            for draw, pool_name in zip(draws, order, strict=True)
        ]
        expect(resolved, case["expected"], f"seed selection {case['seed']}")

    for case in fixture["numerical"]["candidate_generation_cases"]:
        index = case["ideal_index"]
        rounded = round(index)
        candidates = sorted(
            {
                candidate
                for candidate in (rounded, math.floor(index), math.ceil(index), rounded - 1, rounded + 1)
                if candidate >= 1
            }
        )
        expect(candidates, case["expected_indices"], f"candidate case {case['name']}")


    numerical = fixture["numerical"]
    expect(
        numerical["score_order"],
        [
            "max_abs_error",
            "sum_abs_error",
            "abs_pixel_error",
            "abs_aspect_error",
            "native_manhattan_distance",
            "width",
            "height",
        ],
        "score order",
    )
    expect(numerical["error_formula"], "relative_percent", "error formula")
    expect(numerical["native_index_minimum"], 1, "native index minimum")
    for case in fixture["numerical_cases"]:
        best = _oracle_dimensions(case)
        expected = case["expected"]
        expect(expected["width"], best[1], f"width {case['name']}")
        expect(expected["height"], best[2], f"height {case['name']}")
        actual_megapixels = best[1] * best[2] / (1024 * 1024)
        if not math.isclose(
            expected["actual_megapixels"],
            actual_megapixels,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise AssertionError(f"actual megapixels {case['name']} drifted")
        canonical_labels = {tuple(entry["pair"]): entry["label"] for entry in fixture["presets"]}
        expected_label = canonical_labels.get(
            tuple(case["ratio"]), "%d:%d" % _ratio_from_pair(case["ratio"])
        )
        expect(expected["resolved_aspect_ratio"], expected_label, f"ratio label {case['name']}")
        if not math.isclose(expected["pixel_error_percent"], best[3], rel_tol=1e-12, abs_tol=1e-12):
            raise AssertionError(f"pixel diagnostic {case['name']} drifted")
        if not math.isclose(expected["aspect_error_percent"], best[4], rel_tol=1e-12, abs_tol=1e-12):
            raise AssertionError(f"aspect diagnostic {case['name']} drifted")


class AdvancedResolutionSelectorContractTests(unittest.TestCase):
    def test_contract_identity_and_current_stage(self):
        fixture = _load_fixture(self)
        self.assertEqual(
            {
                "id": "TP_AdvancedResolutionSelector",
                "display_name": "Advanced Resolution Selector",
                "category": "ComfyUI Text Processor/Image",
                "function": "select_resolution",
                "api": "v1",
                "classification": "stateless",
            },
            fixture["node"],
        )
        self.assertEqual(
            {
                "name": "T08_unregistered",
                "expected_node_count": 18,
                "expected_visible_input_count": 145,
                "expected_rich_help_count": 9,
                "forbidden_registered_id": "TP_AdvancedResolutionSelector",
            },
            fixture["stage"],
        )

    def test_current_package_stage_is_unregistered(self):
        fixture = _load_fixture(self)
        with PackageImportContext() as package:
            self.assertEqual(
                fixture["stage"]["expected_node_count"],
                len(package.NODE_CLASS_MAPPINGS),
            )
            self.assertNotIn(
                fixture["stage"]["forbidden_registered_id"],
                package.NODE_CLASS_MAPPINGS,
            )
            visible_count = sum(
                len(node_class.INPUT_TYPES().get(group_name, {}))
                for node_class in package.NODE_CLASS_MAPPINGS.values()
                for group_name in ("required", "optional")
            )
            self.assertEqual(fixture["stage"]["expected_visible_input_count"], visible_count)

        docs_dir = REPO_DIR / "web" / "docs"
        self.assertEqual(
            fixture["stage"]["expected_rich_help_count"],
            len([path for path in docs_dir.glob("*.md") if path.is_file()]),
        )

    def test_canonical_preset_and_direction_order(self):
        fixture = _load_fixture(self)
        self.assertEqual(
            ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9"],
            [entry["label"] for entry in fixture["presets"]],
        )
        self.assertEqual(
            [[1, 1], [9, 7], [4, 3], [19, 13], [3, 2], [7, 4], [16, 9], [21, 9]],
            [entry["pair"] for entry in fixture["presets"]],
        )
        self.assertEqual(["landscape", "portrait"], fixture["directions"])
        self.assertEqual("custom", fixture["custom_ratio"]["sentinel"])
        self.assertTrue(fixture["custom_ratio"]["randomize_all_excluded"])
        self.assertEqual(
            len(fixture["presets"]),
            len({tuple(entry["pair"]) for entry in fixture["presets"]}),
        )
        self.assertTrue(all(entry["pair"][0] >= entry["pair"][1] for entry in fixture["presets"]))

    def test_mode_semantics_and_logical_draw_mapping(self):
        fixture = _load_fixture(self)
        modes = fixture["modes"]
        self.assertEqual(
            {
                "ratio_source": "selected",
                "direction_source": "selected",
                "logical_draws": 0,
                "draw_order": [],
            },
            modes["fixed"],
        )
        self.assertEqual(
            {
                "ratio_source": "selected",
                "direction_source": "seeded_random",
                "logical_draws": 1,
                "draw_order": ["direction"],
            },
            modes["randomize"],
        )
        self.assertEqual(
            {
                "ratio_source": "seeded_random_preset",
                "direction_source": "seeded_random",
                "logical_draws": 2,
                "draw_order": ["ratio", "direction"],
            },
            modes["randomize_all"],
        )

        pools = {
            "ratio": [entry["label"] for entry in fixture["presets"]],
            "direction": fixture["directions"],
        }
        for case in fixture["draw_cases"]:
            draws = case["draws"]
            self.assertTrue(all(0.0 <= draw < 1.0 for draw in draws))
            resolved = []
            for draw, pool_name in zip(draws, case["draw_order"], strict=True):
                resolved.append(pools[pool_name][int(draw * len(pools[pool_name]))])
            self.assertEqual(case["expected"], resolved)
            self.assertEqual(case["logical_draws"], len(draws))

    def test_ordered_v1_schema(self):
        fixture = _load_fixture(self)
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
            [entry["name"] for entry in fixture["inputs"]],
        )
        self.assertEqual(
            [
                "width",
                "height",
                "resolved_aspect_ratio",
                "resolved_direction",
                "actual_megapixels",
                "pixel_error_percent",
                "aspect_error_percent",
            ],
            [entry["name"] for entry in fixture["outputs"]],
        )
        self.assertEqual(
            ["INT", "INT", "STRING", "STRING", "FLOAT", "FLOAT", "FLOAT"],
            [entry["type"] for entry in fixture["outputs"]],
        )
        self.assertEqual(
            ["fixed", "1:1", "landscape", 1, 1, 1.0, 8, 0],
            [entry["default"] for entry in fixture["inputs"]],
        )
        self.assertTrue(fixture["inputs"][-1]["control_after_generate"])
        self.assertTrue(fixture["inputs"][3]["advanced"])
        self.assertTrue(fixture["inputs"][4]["advanced"])
        self.assertTrue(fixture["inputs"][6]["advanced"])

    def test_numerical_policy_and_explicit_oracles(self):
        fixture = _load_fixture(self)
        numerical = fixture["numerical"]
        self.assertEqual("binary_1024_squared", numerical["megapixel_unit"])
        self.assertEqual(
            ["round", "floor", "ceil", "round_minus_one", "round_plus_one"],
            numerical["candidate_sources"],
        )
        self.assertEqual(1, numerical["native_index_minimum"])
        self.assertEqual(
            [
                "max_abs_error",
                "sum_abs_error",
                "abs_pixel_error",
                "abs_aspect_error",
                "native_manhattan_distance",
                "width",
                "height",
            ],
            numerical["score_order"],
        )
        self.assertEqual("relative_percent", numerical["error_formula"])
        self.assertEqual(1e-12, numerical["float_tolerance"]["relative"])
        self.assertEqual(1e-12, numerical["float_tolerance"]["absolute"])
        self.assertEqual(0.9999999999999999, numerical["largest_valid_draw"])
        self.assertEqual(
            ["reduced_width:reduced_height", "direction_separate"],
            numerical["custom_label_policy"],
        )
        self.assertEqual(
            [{"input": 2.5, "python_round": 2}, {"input": 3.5, "python_round": 4}],
            numerical["rounding_cases"],
        )

        for case in fixture["numerical_cases"]:
            best = _oracle_dimensions(case)
            self.assertEqual(case["expected"]["width"], best[1], case["name"])
            self.assertEqual(case["expected"]["height"], best[2], case["name"])
            self.assertTrue(
                math.isclose(
                    case["expected"]["actual_megapixels"],
                    best[1] * best[2] / (1024 * 1024),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                case["name"],
            )
            canonical_labels = {tuple(entry["pair"]): entry["label"] for entry in fixture["presets"]}
            expected_label = canonical_labels.get(
                tuple(case["ratio"]), "%d:%d" % _ratio_from_pair(case["ratio"])
            )
            self.assertEqual(case["expected"]["resolved_aspect_ratio"], expected_label, case["name"])
            self.assertTrue(math.isfinite(best[3]), case["name"])
            self.assertTrue(math.isfinite(best[4]), case["name"])
            self.assertTrue(
                math.isclose(
                    case["expected"]["pixel_error_percent"],
                    best[3],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                case["name"],
            )
            self.assertTrue(
                math.isclose(
                    case["expected"]["aspect_error_percent"],
                    best[4],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                case["name"],
            )

        self.assertEqual((3, 2), _ratio_from_pair([6, 4]))
        self.assertEqual((1, 1), _ratio_from_pair([10000, 10000]))
        self.assertEqual(Fraction(3, 2), Fraction(*_ratio_from_pair([6, 4])))

    def test_contract_mutations_are_rejected(self):
        fixture = _load_fixture(self)
        _validate_fixture_contract(fixture)
        mutations = {
            "preset_order": lambda value: value["presets"].reverse(),
            "draw_count": lambda value: value["modes"]["randomize"].update(logical_draws=2),
            "draw_order": lambda value: value["modes"]["randomize_all"].update(
                draw_order=["direction", "ratio"]
            ),
            "reciprocal_duplicate": lambda value: value["presets"][-1].update(pair=[9, 21]),
            "input_position": lambda value: value["inputs"].__setitem__(
                slice(0, 2), value["inputs"][0:2][::-1]
            ),
            "output_position": lambda value: value["outputs"].__setitem__(
                slice(0, 2), value["outputs"][0:2][::-1]
            ),
            "input_bounds": lambda value: value["inputs"][5].update(bounds=[0.2, 16.0]),
            "input_options": lambda value: value["inputs"][0].update(options=["fixed"]),
            "input_tooltip": lambda value: value["inputs"][0].update(tooltip="changed"),
            "score_order": lambda value: value["numerical"].update(
                score_order=["sum_abs_error", "max_abs_error", "abs_pixel_error", "abs_aspect_error", "native_manhattan_distance", "width", "height"]
            ),
            "invalid_diagnostic": lambda value: value["numerical_cases"][0]["expected"].update(
                pixel_error_percent=1.0
            ),
            "invalid_input_case": lambda value: value["invalid_inputs"][0].update(error_id="invalid_multiple"),
            "seed_selection": lambda value: value["seed_cases"][0].update(expected=["landscape"]),
            "halfway_candidate": lambda value: value["numerical"]["candidate_generation_cases"][0].update(
                expected_indices=[1, 2, 4]
            ),
            "provenance": lambda value: value["provenance"][0].update(commit="deadbeef"),
            "premature_registration": lambda value: value["stage"].update(expected_node_count=19),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(fixture)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_fixture_contract(mutated)

    def test_fixture_is_public_safe_and_json_finite(self):
        fixture = _load_fixture(self)
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIsNone(FORBIDDEN_PUBLIC_TEXT.search(text))
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        self.assertNotIn("-Infinity", text)
        self.assertEqual(
            text,
            json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
