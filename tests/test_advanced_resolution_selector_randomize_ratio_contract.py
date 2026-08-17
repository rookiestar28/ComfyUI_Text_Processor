import copy
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import re
import unittest

try:
    import advanced_resolution_selector as adapter
    import advanced_resolution_selector_core as core
except ModuleNotFoundError:
    from .. import advanced_resolution_selector as adapter
    from .. import advanced_resolution_selector_core as core


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_DIR / "tests" / "fixtures"
V2_TARGET_PATH = FIXTURES_DIR / "advanced_resolution_selector_contract_v2.json"
V2_CURRENT_PATH = FIXTURES_DIR / "advanced_resolution_selector_current_stage_v2.json"
V3_TARGET_PATH = FIXTURES_DIR / "advanced_resolution_selector_contract_v3.json"
V3_MIGRATION_PATH = (
    FIXTURES_DIR / "advanced_resolution_selector_mode_migration_v3.json"
)
V3_CURRENT_PATH = FIXTURES_DIR / "advanced_resolution_selector_current_stage_v3.json"
V2_TARGET_SHA256 = "cd2ec31461ae719d217006ac7d800067657e7ad09015e85579b600fb08499cf3"  # pragma: allowlist secret
V2_CURRENT_SHA256 = "c277bbd230dc7e018bc063c6815d0d476a8cd5cf2b8d4a8ad7e0107c5a31f496"  # pragma: allowlist secret
OUTPUT_MODES = ["fixed", "randomize", "randomize_all", "randomize_ratio"]
RATIO_POOL = ["9:7", "4:3", "19:13", "3:2", "7:4", "16:9"]
INPUT_ORDER = [
    "output_mode",
    "aspect_ratio",
    "direction",
    "custom_ratio_width",
    "custom_ratio_height",
    "megapixels",
    "multiple",
    "seed",
]
OUTPUT_ORDER = [
    "width",
    "height",
    "resolved_aspect_ratio",
    "resolved_direction",
    "actual_megapixels",
    "pixel_error_percent",
    "aspect_error_percent",
]
OUTPUT_MODE_TOOLTIP = (
    "Select fixed, seeded direction randomization, seeded preset and direction "
    "randomization, or seeded ratio randomization with the selected direction."
)
DIRECTION_TOOLTIP = (
    "Choose the resolved orientation; randomize and randomize_all may replace it, "
    "while fixed and randomize_ratio preserve it."
)
FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference[/\\]|ROADMAP\.md|"
    r"command[ _-]?log|implementation[ _-]?record|api[_ -]?key|authorization:|"
    r"cookie|secret|token|prompt)"
)


class DrawRecorder:
    def __init__(self, draws):
        self._draws = iter(draws)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        try:
            return next(self._draws)
        except StopIteration as exc:
            raise AssertionError("unexpected draw") from exc


def _load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha_chunks(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return [digest[index : index + 8] for index in range(0, len(digest), 8)]


def _new_draw_cases():
    selected_ratios = ["1:1", "custom", "21:9", "1:1", "custom", "21:9"]
    selected_directions = [
        "portrait",
        "landscape",
        "portrait",
        "landscape",
        "portrait",
        "landscape",
    ]
    cases = []
    for index, (selected_ratio, selected_direction) in enumerate(
        zip(selected_ratios, selected_directions, strict=True)
    ):
        cases.append(
            {
                "draw_order": ["ratio"],
                "draws": [index / len(RATIO_POOL)],
                "expected": [RATIO_POOL[index], selected_direction],
                "logical_draws": 1,
                "mode": "randomize_ratio",
                "selected_aspect_ratio": selected_ratio,
                "selected_direction": selected_direction,
            }
        )
    cases.append(
        {
            "draw_order": ["ratio"],
            "draws": [0.9999999999999999],
            "expected": ["16:9", "portrait"],
            "logical_draws": 1,
            "mode": "randomize_ratio",
            "selected_aspect_ratio": "1:1",
            "selected_direction": "portrait",
        }
    )
    return cases


def _new_seed_cases():
    return [
        {
            "draws": [0.8444218515250481],
            "expected": ["16:9", "portrait"],
            "mode": "randomize_ratio",
            "seed": 0,
            "selected_direction": "portrait",
        },
        {
            "draws": [0.13436424411240122],
            "expected": ["9:7", "landscape"],
            "mode": "randomize_ratio",
            "seed": 1,
            "selected_direction": "landscape",
        },
        {
            "draws": [0.6353574441341173],
            "expected": ["3:2", "portrait"],
            "mode": "randomize_ratio",
            "seed": 4294967295,
            "selected_direction": "portrait",
        },
    ]


def _expected_v3_target(v2):
    expected = copy.deepcopy(v2)
    expected["schema_version"] = 3
    expected["inputs"][0]["options"] = OUTPUT_MODES
    expected["inputs"][0]["tooltip"] = OUTPUT_MODE_TOOLTIP
    expected["inputs"][2]["tooltip"] = DIRECTION_TOOLTIP
    expected["modes"]["randomize_ratio"] = {
        "direction_source": "selected",
        "draw_order": ["ratio"],
        "logical_draws": 1,
        "ratio_pool_labels": RATIO_POOL,
        "ratio_source": "seeded_random_public_preset_excluding_1_1",
    }
    expected["draw_cases"].extend(_new_draw_cases())
    expected["seed_cases"].extend(_new_seed_cases())
    return expected


def _validate_target(v2, target):
    if target != _expected_v3_target(v2):
        raise AssertionError("v3 target contains an unauthorized or missing delta")


def _expected_migration():
    cases = [
        ("fixed_existing", ["fixed", "16:9", "portrait", 1, 1, 1.0, 8, 0]),
        (
            "randomize_existing",
            ["randomize", "4:3", "landscape", 1, 1, 1.0, 8, 1],
        ),
        (
            "randomize_all_existing",
            ["randomize_all", "custom", "portrait", 2, 1, 1.0, 8, 0],
        ),
        (
            "randomize_ratio_new",
            ["randomize_ratio", "1:1", "portrait", 1, 1, 1.0, 8, 0],
        ),
    ]
    return {
        "schema_version": 3,
        "source_contract": {
            "filename": V2_TARGET_PATH.name,
            "sha256_hex_chunks": _sha_chunks(V2_TARGET_PATH),
        },
        "target_contract": {
            "filename": V3_TARGET_PATH.name,
            "sha256_hex_chunks": _sha_chunks(V3_TARGET_PATH),
        },
        "supported_frontend_tiers": [
            {"id": "desktop_floor", "version": "1.43.18"},
            {"id": "current", "version": "1.49.1"},
        ],
        "input_order": INPUT_ORDER,
        "output_order": OUTPUT_ORDER,
        "public_output_modes": OUTPUT_MODES,
        "legacy_recognized_ratio_labels": ["21:9"],
        "cases": [
            {
                "id": case_id,
                "tiers": ["desktop_floor", "current"],
                "serialized_widgets": vector,
                "expected_restored_widgets": vector,
                "expected_serialized_widgets": vector,
            }
            for case_id, vector in cases
        ],
    }


def _validate_migration(migration):
    if list(migration) != [
        "schema_version",
        "source_contract",
        "target_contract",
        "supported_frontend_tiers",
        "input_order",
        "output_order",
        "public_output_modes",
        "legacy_recognized_ratio_labels",
        "cases",
    ]:
        raise AssertionError("migration top-level order drifted")
    if migration != _expected_migration():
        raise AssertionError("migration contract contains an unauthorized delta")


def _expected_current_stage():
    return {
        "schema_version": 3,
        "source_boundaries": {
            "canonical_presets_alias": "PUBLIC_PRESETS",
            "randomize_ratio_presets_alias": "RANDOMIZE_RATIO_PRESETS",
            "legacy_preset_labels": ["21:9"],
            "legacy_execution_modes": ["fixed", "randomize"],
            "public_preset_labels": ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9"],
            "randomize_ratio_preset_labels": RATIO_POOL,
            "recognized_ratio_labels": ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "21:9"],
            "output_modes": OUTPUT_MODES,
            "input_order": INPUT_ORDER,
            "output_order": OUTPUT_ORDER,
        },
        "stage": {"implementation_status": "implemented", "name": "current_product"},
        "target_contract": {
            "filename": V3_TARGET_PATH.name,
            "sha256_hex_chunks": _sha_chunks(V3_TARGET_PATH),
        },
        "validator_inputs": ["aspect_ratio"],
    }


def _validate_current_stage(current):
    if current != _expected_current_stage():
        raise AssertionError("current-stage v3 binding drifted")


def _valid_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _target_select(target, draw_stream=None, **overrides):
    values = {
        "output_mode": "randomize_ratio",
        "aspect_ratio": "1:1",
        "direction": "landscape",
        "custom_ratio_width": 1,
        "custom_ratio_height": 1,
        "megapixels": 1.0,
        "multiple": 8,
        "seed": 0,
    }
    values.update(overrides)
    options = target["inputs"][1]["options"] + ["21:9"]
    if values["output_mode"] != "randomize_ratio":
        raise ValueError("invalid_output_mode")
    if values["aspect_ratio"] not in options:
        raise ValueError("invalid_aspect_ratio")
    for key in ("custom_ratio_width", "custom_ratio_height"):
        if not _valid_integer(values[key]) or not 1 <= values[key] <= 10000:
            raise ValueError("invalid_ratio")
    if values["direction"] not in ("landscape", "portrait"):
        raise ValueError("invalid_direction")
    megapixels = values["megapixels"]
    if (
        isinstance(megapixels, bool)
        or not isinstance(megapixels, (int, float))
        or not math.isfinite(float(megapixels))
        or not 0.1 <= megapixels <= 16.0
    ):
        raise ValueError("invalid_megapixels")
    multiple = values["multiple"]
    if (
        not _valid_integer(multiple)
        or not 8 <= multiple <= 128
        or (multiple - 8) % 4
    ):
        raise ValueError("invalid_multiple")
    seed = values["seed"]
    if not _valid_integer(seed) or not 0 <= seed <= 4294967295:
        raise ValueError("invalid_seed")

    stream = draw_stream if draw_stream is not None else random.Random(seed).random
    if not callable(stream):
        raise ValueError("invalid_draw_stream")
    draw = stream()
    if (
        isinstance(draw, bool)
        or not isinstance(draw, (int, float))
        or not math.isfinite(float(draw))
        or not 0.0 <= draw < 1.0
    ):
        raise ValueError("invalid_draw")
    pool = target["modes"]["randomize_ratio"]["ratio_pool_labels"]
    return pool[int(float(draw) * len(pool))], values["direction"]


class AdvancedResolutionSelectorRandomizeRatioContractTests(unittest.TestCase):
    def test_required_v3_fixtures_exist(self):
        self.assertTrue(
            V3_TARGET_PATH.is_file(),
            "required v3 target fixture is missing",
        )
        self.assertTrue(
            V3_MIGRATION_PATH.is_file(),
            "required v3 migration fixture is missing",
        )

    def test_target_is_exact_v2_to_v3_allowlist(self):
        v2 = _load(V2_TARGET_PATH)
        target = _load(V3_TARGET_PATH)
        _validate_target(v2, target)
        self.assertEqual("target_contract", target["stage"]["name"])
        self.assertEqual("not_implemented", target["stage"]["implementation_status"])
        self.assertEqual(["fixed", "randomize"], target["legacy_presets"][0]["execution_modes"])

    def test_target_mutations_are_rejected(self):
        v2 = _load(V2_TARGET_PATH)
        target = _load(V3_TARGET_PATH)
        mutations = {
            "option_reorder": lambda value: value["inputs"][0]["options"].reverse(),
            "mode_missing": lambda value: value["modes"].pop("randomize_ratio"),
            "pool_1_1": lambda value: value["modes"]["randomize_ratio"][
                "ratio_pool_labels"
            ].insert(0, "1:1"),
            "pool_custom": lambda value: value["modes"]["randomize_ratio"][
                "ratio_pool_labels"
            ].append("custom"),
            "pool_legacy": lambda value: value["modes"]["randomize_ratio"][
                "ratio_pool_labels"
            ].append("21:9"),
            "extra_direction_draw": lambda value: value["modes"]["randomize_ratio"].update(
                draw_order=["ratio", "direction"], logical_draws=2
            ),
            "direction_replaced": lambda value: value["modes"]["randomize_ratio"].update(
                direction_source="seeded_random"
            ),
            "existing_mode_drift": lambda value: value["modes"]["randomize_all"].update(
                draw_order=["direction", "ratio"]
            ),
            "legacy_emission_drift": lambda value: value["legacy_presets"][0][
                "execution_modes"
            ].append("randomize_ratio"),
            "tooltip_drift": lambda value: value["inputs"][0].update(tooltip="changed"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(target)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_target(v2, mutated)

    def test_current_product_binds_exact_v3_target_and_live_source(self):
        self.assertTrue(V3_CURRENT_PATH.is_file(), "required current-stage v3 fixture is missing")
        current = _load(V3_CURRENT_PATH)
        _validate_current_stage(current)
        boundary = current["source_boundaries"]
        required = adapter.AdvancedResolutionSelector.INPUT_TYPES()["required"]
        self.assertEqual(boundary["output_modes"], list(adapter.OUTPUT_MODES))
        self.assertEqual(boundary["output_modes"], list(required["output_mode"][0]))
        self.assertEqual(boundary["input_order"], list(required))
        self.assertEqual(boundary["output_order"], list(adapter.AdvancedResolutionSelector.RETURN_NAMES))
        self.assertEqual(boundary["public_preset_labels"], [ratio.label for ratio in core.PUBLIC_PRESETS])
        self.assertEqual(boundary["randomize_ratio_preset_labels"], [ratio.label for ratio in adapter.RANDOMIZE_RATIO_PRESETS])
        self.assertTrue(all(any(ratio is public for public in core.PUBLIC_PRESETS) for ratio in adapter.RANDOMIZE_RATIO_PRESETS))
        self.assertEqual(tuple(boundary["legacy_preset_labels"]), core.LEGACY_PRESET_LABELS)
        self.assertEqual(boundary["recognized_ratio_labels"], [label for label, _pair in core.RECOGNIZED_RATIO_PAIRS])
        self.assertEqual(["aspect_ratio"], list(inspect.signature(adapter.AdvancedResolutionSelector.VALIDATE_INPUTS).parameters))

    def test_current_stage_mutations_are_rejected(self):
        current = _load(V3_CURRENT_PATH)
        mutations = {
            "target_hash": lambda value: value["target_contract"]["sha256_hex_chunks"].__setitem__(0, "00000000"),
            "pool": lambda value: value["source_boundaries"]["randomize_ratio_preset_labels"].insert(0, "1:1"),
            "mode_order": lambda value: value["source_boundaries"]["output_modes"].reverse(),
            "validator": lambda value: value.update(validator_inputs=["output_mode", "aspect_ratio"]),
            "legacy_modes": lambda value: value["source_boundaries"].update(legacy_execution_modes=["fixed", "randomize", "randomize_ratio"]),
            "stage": lambda value: value["stage"].update(implementation_status="not_implemented"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(current)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_current_stage(mutated)

    def test_six_bucket_endpoints_replace_selected_values_and_preserve_direction(self):
        target = _load(V3_TARGET_PATH)
        new_cases = target["draw_cases"][-7:]
        self.assertEqual(_new_draw_cases(), new_cases)
        for case in new_cases:
            recorder = DrawRecorder(case["draws"])
            actual = _target_select(
                target,
                recorder,
                aspect_ratio=case["selected_aspect_ratio"],
                direction=case["selected_direction"],
            )
            with self.subTest(draw=case["draws"][0]):
                self.assertEqual(tuple(case["expected"]), actual)
                self.assertEqual(1, recorder.calls)
                self.assertNotIn(actual[0], ("1:1", "custom", "21:9"))

    def test_seed_mapping_is_reproducible_and_global_rng_isolated(self):
        target = _load(V3_TARGET_PATH)
        self.assertEqual(_new_seed_cases(), target["seed_cases"][-3:])
        state = random.getstate()
        for case in target["seed_cases"][-3:]:
            first = _target_select(
                target,
                seed=case["seed"],
                direction=case["selected_direction"],
            )
            second = _target_select(
                target,
                seed=case["seed"],
                direction=case["selected_direction"],
            )
            with self.subTest(seed=case["seed"]):
                self.assertEqual(tuple(case["expected"]), first)
                self.assertEqual(first, second)
        self.assertEqual(state, random.getstate())

    def test_validation_precedes_rng_and_invalid_draws_fail_at_boundary(self):
        target = _load(V3_TARGET_PATH)
        invalid = (
            ("output_mode", "unknown"),
            ("aspect_ratio", "2:1"),
            ("custom_ratio_width", 0),
            ("custom_ratio_height", True),
            ("direction", "diagonal"),
            ("megapixels", float("nan")),
            ("multiple", 10),
            ("seed", 4294967296),
        )
        for key, value in invalid:
            recorder = DrawRecorder([0.0])
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    _target_select(target, recorder, **{key: value})
                self.assertEqual(0, recorder.calls)
        for draw in (-0.1, 1.0, float("nan"), True, "0"):
            recorder = DrawRecorder([draw])
            with self.subTest(draw=draw):
                with self.assertRaisesRegex(ValueError, "^invalid_draw$"):
                    _target_select(target, recorder)
                self.assertEqual(1, recorder.calls)

    def test_migration_contract_is_exact_and_round_trips_both_tiers(self):
        migration = _load(V3_MIGRATION_PATH)
        _validate_migration(migration)
        for case in migration["cases"]:
            restored = dict(
                zip(migration["input_order"], case["serialized_widgets"], strict=True)
            )
            serialized = [restored[name] for name in migration["input_order"]]
            with self.subTest(case=case["id"]):
                self.assertEqual(case["expected_restored_widgets"], serialized)
                self.assertEqual(case["expected_serialized_widgets"], serialized)
                self.assertEqual(["desktop_floor", "current"], case["tiers"])

    def test_migration_mutations_are_rejected(self):
        migration = _load(V3_MIGRATION_PATH)
        mutations = {
            "option_reorder": lambda value: value["public_output_modes"].reverse(),
            "mode_missing": lambda value: value["public_output_modes"].pop(),
            "legacy_lost": lambda value: value.update(legacy_recognized_ratio_labels=[]),
            "input_order": lambda value: value["input_order"].reverse(),
            "output_order": lambda value: value["output_order"].reverse(),
            "tier_drift": lambda value: value["supported_frontend_tiers"][0].update(
                version="1.43.19"
            ),
            "old_mode_substitution": lambda value: value["cases"][0][
                "expected_serialized_widgets"
            ].__setitem__(0, "randomize_ratio"),
            "new_mode_substitution": lambda value: value["cases"][3][
                "expected_restored_widgets"
            ].__setitem__(0, "fixed"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(migration)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_migration(mutated)

    def test_accepted_v2_binding_and_bytes_remain_exact(self):
        self.assertEqual(V2_TARGET_SHA256, hashlib.sha256(V2_TARGET_PATH.read_bytes()).hexdigest())
        self.assertEqual(V2_CURRENT_SHA256, hashlib.sha256(V2_CURRENT_PATH.read_bytes()).hexdigest())
        current = _load(V2_CURRENT_PATH)
        self.assertEqual(V2_TARGET_PATH.name, current["target_contract"]["filename"])
        self.assertEqual(V2_TARGET_SHA256, "".join(current["target_contract"]["sha256_hex_chunks"]))

    def test_v3_fixtures_are_canonical_lf_and_public_safe(self):
        target = _load(V3_TARGET_PATH)
        migration = _load(V3_MIGRATION_PATH)
        current = _load(V3_CURRENT_PATH)
        for path, fixture, sort_keys in (
            (V3_TARGET_PATH, target, True),
            (V3_MIGRATION_PATH, migration, False),
            (V3_CURRENT_PATH, current, False),
        ):
            with self.subTest(path=path.name):
                data = path.read_bytes()
                text = data.decode("utf-8")
                self.assertNotIn(b"\r", data)
                self.assertTrue(data.endswith(b"\n"))
                self.assertIsNone(FORBIDDEN_PUBLIC_TEXT.search(text))
                self.assertNotIn("NaN", text)
                self.assertNotIn("Infinity", text)
                self.assertEqual(
                    json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=sort_keys)
                    + "\n",
                    text,
                )


if __name__ == "__main__":
    unittest.main()
