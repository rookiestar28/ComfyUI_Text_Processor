import copy
import hashlib
import json
from pathlib import Path
import re
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_DIR / "tests" / "fixtures"
V1_CONTRACT_PATH = FIXTURES_DIR / "advanced_resolution_selector_contract_v1.json"
V2_CONTRACT_PATH = FIXTURES_DIR / "advanced_resolution_selector_contract_v2.json"
V1_WORKFLOWS_PATH = FIXTURES_DIR / "legacy_workflows_v1.json"
V2_MIGRATION_PATH = FIXTURES_DIR / "advanced_resolution_selector_legacy_migration_v2.json"
CURRENT_STAGE_PATH = FIXTURES_DIR / "advanced_resolution_selector_current_stage_v2.json"
V1_CONTRACT_SHA256 = "b9c26767ac1a4cb4b3f4513585014f7e2a14f1d05a8eb2fb11be960059c31514"  # pragma: allowlist secret
V1_WORKFLOWS_SHA256 = "361a06896f0143b9348e40d7637c7af64e99854273d7886729366d5b8c82aaa1"  # pragma: allowlist secret
V2_CONTRACT_SHA256 = "cd2ec31461ae719d217006ac7d800067657e7ad09015e85579b600fb08499cf3"  # pragma: allowlist secret
V2_MIGRATION_SHA256 = "549a506a525ef971fad231304f87db2e0f07e596e572120a99775f46c625456c"  # pragma: allowlist secret
PUBLIC_PRESETS = ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9"]
PUBLIC_OPTIONS = PUBLIC_PRESETS + ["custom"]
INPUT_IDS = [
    "output_mode",
    "aspect_ratio",
    "direction",
    "custom_ratio_width",
    "custom_ratio_height",
    "megapixels",
    "multiple",
    "seed",
]
FORBIDDEN_FIXTURE_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference[/\\]|ROADMAP\.md|"
    r"command[ _-]?log|implementation[ _-]?record|api[_ -]?key|authorization:|"
    r"cookie|secret|token|prompt)"
)


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _load_required_fixture(test_case, path):
    test_case.assertTrue(path.is_file(), f"required v2 fixture is missing: {path.name}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _expected_target_draw_cases(current):
    cases = copy.deepcopy(current["draw_cases"][:3])
    for index, label in enumerate(PUBLIC_PRESETS):
        cases.append(
            {
                "draw_order": ["ratio", "direction"],
                "draws": [index / len(PUBLIC_PRESETS), 0.0],
                "expected": [label, "landscape"],
                "logical_draws": 2,
                "mode": "randomize_all",
            }
        )
    cases.append(
        {
            "draw_order": ["ratio", "direction"],
            "draws": [0.9999999999999999, 0.9999999999999999],
            "expected": ["16:9", "portrait"],
            "logical_draws": 2,
            "mode": "randomize_all",
        }
    )
    return cases


def _expected_target_seed_cases(current):
    cases = copy.deepcopy(current["seed_cases"])
    directions = current["directions"]
    for case in cases:
        if case["mode"] != "randomize_all":
            continue
        ratio_index = int(case["draws"][0] * len(PUBLIC_PRESETS))
        direction_index = int(case["draws"][1] * len(directions))
        case["expected"] = [PUBLIC_PRESETS[ratio_index], directions[direction_index]]
    return cases


def _validate_target_contract(current, target):
    _require(
        set(target) == set(current) | {"legacy_presets"},
        "target top-level fields must be the v1 fields plus legacy_presets",
    )
    _require(target["schema_version"] == 2, "target schema_version must be 2")

    expected_stage = copy.deepcopy(current["stage"])
    expected_stage["name"] = "target_contract"
    expected_stage["implementation_status"] = "not_implemented"
    _require(target["stage"] == expected_stage, "target stage marker or counts drifted")

    expected_presets = current["presets"][:-1]
    _require(target["presets"] == expected_presets, "target public preset list drifted")
    _require(
        [entry["label"] for entry in target["presets"]] == PUBLIC_PRESETS,
        "target preset labels must be the frozen seven-label order",
    )
    normalized_pairs = {
        tuple(sorted(entry["pair"]))
        for entry in target["presets"]
    }
    _require(
        len(normalized_pairs) == len(target["presets"]),
        "target presets must not contain reciprocal duplicates",
    )

    expected_legacy = [
        {
            "execution_modes": ["fixed", "randomize"],
            "label": "21:9",
            "pair": [21, 9],
            "randomize_all_excluded": True,
            "selectable": False,
        }
    ]
    _require(target["legacy_presets"] == expected_legacy, "legacy 21:9 metadata drifted")

    expected_inputs = copy.deepcopy(current["inputs"])
    expected_inputs[1]["options"] = PUBLIC_OPTIONS
    _require(target["inputs"] == expected_inputs, "target input contract has an unauthorized delta")
    _require(
        [entry["name"] for entry in target["inputs"]] == INPUT_IDS,
        "stable eight-input order drifted",
    )

    unchanged_fields = (
        "custom_ratio",
        "directions",
        "invalid_inputs",
        "modes",
        "node",
        "numerical",
        "numerical_cases",
        "outputs",
        "provenance",
        "validation",
    )
    for field in unchanged_fields:
        _require(target[field] == current[field], f"unauthorized target delta: {field}")

    _require(
        target["draw_cases"] == _expected_target_draw_cases(current),
        "seven-bucket draw cases or endpoint mapping drifted",
    )
    _require(
        target["seed_cases"] == _expected_target_seed_cases(current),
        "seven-bucket seeded mapping drifted",
    )


def _validate_migration_fixture(fixture):
    _require(
        set(fixture)
        == {
            "contract",
            "custom_ratio_presentation",
            "frontend_tiers",
            "input_ids",
            "node_id",
            "schema_version",
            "selectable_aspect_ratios",
            "synthetic_only",
            "widget_values",
        },
        "migration fixture fields drifted",
    )
    _require(fixture["schema_version"] == 2, "migration schema_version must be 2")
    _require(
        fixture["contract"] == "advanced_resolution_selector_legacy_migration",
        "migration contract identity drifted",
    )
    _require(fixture["synthetic_only"] is True, "migration evidence must remain synthetic")
    _require(
        fixture["node_id"] == "TP_AdvancedResolutionSelector",
        "migration node identity drifted",
    )
    _require(fixture["input_ids"] == INPUT_IDS, "migration input order drifted")
    _require(
        fixture["selectable_aspect_ratios"] == PUBLIC_OPTIONS,
        "migration selectable options drifted",
    )
    _require("21:9" not in fixture["selectable_aspect_ratios"], "legacy value became selectable")
    _require(
        fixture["frontend_tiers"]
        == [
            {
                "id": "desktop_floor",
                "source": "synthetic_pinned_source_contract",
                "version": "1.43.18",
            },
            {
                "id": "current_reference",
                "source": "synthetic_pinned_source_contract",
                "version": "1.49.1",
            },
        ],
        "synthetic Frontend tier descriptors drifted",
    )
    _require(
        fixture["widget_values"] == ["fixed", "21:9", "landscape", 1, 1, 1.0, 8, 0],
        "legacy positional widget vector drifted",
    )
    _require(
        fixture["custom_ratio_presentation"]
        == {
            "custom_ratio_height": {
                "label": "custom_ratio_height",
                "tooltip": "Positive custom ratio height; used when aspect_ratio is custom.",
            },
            "custom_ratio_width": {
                "label": "custom_ratio_width",
                "tooltip": "Positive custom ratio width; used when aspect_ratio is custom.",
            },
        },
        "custom-ratio presentation drifted",
    )
    restored = dict(zip(fixture["input_ids"], fixture["widget_values"], strict=True))
    _require(restored["aspect_ratio"] == "21:9", "legacy aspect_ratio restore drifted")
    serialized = [restored[input_id] for input_id in fixture["input_ids"]]
    _require(serialized == fixture["widget_values"], "legacy positional serialization drifted")


def _validate_current_stage_fixture(fixture):
    expected = {
        "schema_version": 2,
        "stage": {
            "implementation_status": "implemented",
            "name": "current_product",
        },
        "target_contract": {
            "filename": "advanced_resolution_selector_contract_v2.json",
            "sha256_hex_chunks": [
                "cd2ec314",
                "61ae719d",
                "217006ac",
                "7d800067",
                "657e7ad0",
                "9015e855",
                "79b600fb",
                "08499cf3",
            ],
        },
        "source_boundaries": {
            "canonical_presets_alias": "PUBLIC_PRESETS",
            "legacy_preset_labels": ["21:9"],
            "public_preset_labels": PUBLIC_PRESETS,
            "recognized_ratio_labels": PUBLIC_PRESETS + ["21:9"],
        },
    }
    _require(fixture == expected, "current-stage product binding drifted")
    _require(
        "".join(fixture["target_contract"]["sha256_hex_chunks"])
        == V2_CONTRACT_SHA256,
        "current-stage target hash drifted",
    )


class AdvancedResolutionSelectorMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with V1_CONTRACT_PATH.open(encoding="utf-8") as handle:
            cls.current = json.load(handle)

    def test_accepted_v1_fixtures_remain_byte_for_byte_unchanged(self):
        self.assertEqual(
            V1_CONTRACT_SHA256,
            hashlib.sha256(V1_CONTRACT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V1_WORKFLOWS_SHA256,
            hashlib.sha256(V1_WORKFLOWS_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V2_CONTRACT_SHA256,
            hashlib.sha256(V2_CONTRACT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V2_MIGRATION_SHA256,
            hashlib.sha256(V2_MIGRATION_PATH.read_bytes()).hexdigest(),
        )

    def test_current_stage_binding_is_canonical_and_binds_immutable_target(self):
        current_stage = _load_required_fixture(self, CURRENT_STAGE_PATH)
        _validate_current_stage_fixture(current_stage)
        self.assertEqual(
            "".join(current_stage["target_contract"]["sha256_hex_chunks"]),
            hashlib.sha256(V2_CONTRACT_PATH.read_bytes()).hexdigest(),
        )

    def test_current_product_matches_bound_target_and_named_source_boundaries(self):
        current_stage = _load_required_fixture(self, CURRENT_STAGE_PATH)
        target = _load_required_fixture(self, V2_CONTRACT_PATH)

        try:
            import advanced_resolution_selector as adapter
            import advanced_resolution_selector_core as core
        except ModuleNotFoundError:
            from .. import advanced_resolution_selector as adapter
            from .. import advanced_resolution_selector_core as core

        boundary = current_stage["source_boundaries"]
        self.assertEqual(
            boundary["recognized_ratio_labels"],
            [label for label, _pair in core.RECOGNIZED_RATIO_PAIRS],
        )
        self.assertEqual(
            boundary["public_preset_labels"],
            [ratio.label for ratio in core.PUBLIC_PRESETS],
        )
        self.assertEqual(tuple(boundary["legacy_preset_labels"]), core.LEGACY_PRESET_LABELS)
        self.assertIs(core.CANONICAL_PRESETS, core.PUBLIC_PRESETS)
        self.assertEqual(PUBLIC_OPTIONS, list(adapter.ASPECT_RATIO_OPTIONS))
        self.assertEqual(PUBLIC_PRESETS, list(adapter.RATIO_LABELS))
        self.assertEqual(
            target["inputs"][1]["options"],
            list(adapter.AdvancedResolutionSelector.INPUT_TYPES()["required"]["aspect_ratio"][0]),
        )

    def test_current_stage_binding_mutations_are_rejected(self):
        current_stage = _load_required_fixture(self, CURRENT_STAGE_PATH)
        mutations = {
            "target_hash": lambda value: value["target_contract"][
                "sha256_hex_chunks"
            ].__setitem__(0, "0" * 8),
            "legacy_boundary": lambda value: value["source_boundaries"].update(
                legacy_preset_labels=[]
            ),
            "public_boundary": lambda value: value["source_boundaries"][
                "public_preset_labels"
            ].append("21:9"),
            "stage": lambda value: value["stage"].update(
                implementation_status="not_implemented"
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(current_stage)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_current_stage_fixture(mutated)

    def test_target_contract_allows_only_the_finalized_v1_to_v2_delta(self):
        target = _load_required_fixture(self, V2_CONTRACT_PATH)
        _validate_target_contract(self.current, target)

    def test_target_contract_mutations_are_rejected(self):
        target = _load_required_fixture(self, V2_CONTRACT_PATH)
        mutations = {
            "stage_missing": lambda value: value["stage"].pop("implementation_status"),
            "legacy_missing": lambda value: value.update(legacy_presets=[]),
            "legacy_selectable": lambda value: value["legacy_presets"][0].update(
                selectable=True
            ),
            "21_9_public": lambda value: value["inputs"][1]["options"].insert(-1, "21:9"),
            "reciprocal_duplicate": lambda value: value["presets"].append(
                {"label": "9:16", "pair": [9, 16]}
            ),
            "input_order": lambda value: value["inputs"].__setitem__(
                slice(3, 5), value["inputs"][3:5][::-1]
            ),
            "custom_tooltip": lambda value: value["inputs"][3].update(tooltip="changed"),
            "legacy_oracle": lambda value: value["numerical_cases"][1]["expected"].update(
                resolved_aspect_ratio="16:9"
            ),
            "ratio_draw_order": lambda value: value["modes"]["randomize_all"].update(
                draw_order=["direction", "ratio"]
            ),
            "bucket_mapping": lambda value: value["draw_cases"][3].update(
                expected=["9:7", "landscape"]
            ),
            "seed_mapping": lambda value: value["seed_cases"][2].update(
                expected=["21:9", "portrait"]
            ),
            "node_identity": lambda value: value["node"].update(id="ResolutionSelector"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(target)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_target_contract(self.current, mutated)

    def test_migration_fixture_freezes_synthetic_restore_and_serialization(self):
        migration = _load_required_fixture(self, V2_MIGRATION_PATH)
        _validate_migration_fixture(migration)

    def test_migration_fixture_mutations_are_rejected(self):
        migration = _load_required_fixture(self, V2_MIGRATION_PATH)
        mutations = {
            "floor_version": lambda value: value["frontend_tiers"][0].update(
                version="1.43.19"
            ),
            "legacy_option_reintroduced": lambda value: value[
                "selectable_aspect_ratios"
            ].insert(-1, "21:9"),
            "stored_value_dropped": lambda value: value["widget_values"].pop(1),
            "stored_value_substituted": lambda value: value["widget_values"].__setitem__(
                1, "16:9"
            ),
            "input_order": lambda value: value["input_ids"].__setitem__(
                slice(0, 2), value["input_ids"][0:2][::-1]
            ),
            "presentation": lambda value: value["custom_ratio_presentation"][
                "custom_ratio_width"
            ].update(label="custom ratio width component"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(migration)
                mutate(mutated)
                with self.assertRaises(AssertionError):
                    _validate_migration_fixture(mutated)

    def test_v2_fixtures_are_canonical_json_and_public_safe(self):
        for path in (V2_CONTRACT_PATH, V2_MIGRATION_PATH, CURRENT_STAGE_PATH):
            with self.subTest(path=path.name):
                fixture = _load_required_fixture(self, path)
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(FORBIDDEN_FIXTURE_TEXT.search(text))
                self.assertNotIn("NaN", text)
                self.assertNotIn("Infinity", text)
                self.assertEqual(
                    text,
                    json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                )


if __name__ == "__main__":
    unittest.main()
