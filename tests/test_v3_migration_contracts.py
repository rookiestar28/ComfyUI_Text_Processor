import importlib.util
import json
import re
import unittest
from collections import Counter
from pathlib import Path

from test_host_compatibility_contracts import (
    PackageImportContext,
    _normalize_node_contract,
    _widget_input_names,
)


TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
MIGRATION_CONTRACT_PATH = FIXTURES_DIR / "v3_migration_contracts_v1.json"
PROTOTYPE_WORKFLOWS_PATH = FIXTURES_DIR / "v3_text_input_workflows_v1.json"
PROTOTYPE_PATH = TESTS_DIR / "v3_text_input_prototype.py"
PROJECT_ROOT = TESTS_DIR.parent
ALLOWED_CLASSIFICATIONS = {
    "stateless",
    "external_stateful",
    "class_stateful",
    "instance_stateful",
}
FORBIDDEN_FIXTURE_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference/docs|authorization|cookie|secret|token)"
)


class _FakeStringInput:
    io_type = "STRING"

    def __init__(
        self,
        id,
        display_name=None,
        optional=False,
        tooltip=None,
        multiline=False,
        placeholder=None,
        default=None,
        dynamic_prompts=None,
    ):
        self.id = id
        self.display_name = display_name
        self.optional = optional
        self.tooltip = tooltip
        self.multiline = multiline
        self.placeholder = placeholder
        self.default = default
        self.dynamic_prompts = dynamic_prompts


class _FakeStringOutput:
    io_type = "STRING"

    def __init__(self, id=None, display_name=None, tooltip=None):
        self.id = id
        self.display_name = display_name
        self.tooltip = tooltip


class _FakeString:
    Input = _FakeStringInput
    Output = _FakeStringOutput


class _FakeSchema:
    def __init__(
        self,
        *,
        node_id,
        display_name=None,
        category="sd",
        description="",
        search_aliases=None,
        inputs=None,
        outputs=None,
        hidden=None,
        is_output_node=False,
    ):
        self.node_id = node_id
        self.display_name = display_name
        self.category = category
        self.description = description
        self.search_aliases = list(search_aliases or [])
        self.inputs = list(inputs or [])
        self.outputs = list(outputs or [])
        self.hidden = list(hidden or [])
        self.is_output_node = is_output_node


class _FakeNodeOutput:
    def __init__(self, *args, ui=None):
        self.args = args
        self.ui = ui

    @property
    def result(self):
        return self.args if self.args else None


class _FakeComfyNode:
    pass


class _FakeIO:
    ComfyNode = _FakeComfyNode
    Schema = _FakeSchema
    String = _FakeString
    NodeOutput = _FakeNodeOutput

    def __init__(self, tier_id):
        self.tier_id = tier_id


def _load_json(path):
    with open(path, encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _load_prototype_module():
    spec = importlib.util.spec_from_file_location(
        "v3_text_input_prototype",
        PROTOTYPE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_v3_schema(schema):
    normalized = {"required": [], "optional": [], "hidden": []}
    for input_spec in schema.inputs:
        group = "optional" if input_spec.optional else "required"
        normalized[group].append(
            {
                "name": input_spec.id,
                "type": input_spec.io_type,
                "default": input_spec.default,
                "widget": True,
            }
        )

    return {
        **normalized,
        "outputs": [
            {
                "index": index,
                "type": output.io_type,
                "name": output.display_name or output.id or output.io_type,
            }
            for index, output in enumerate(schema.outputs)
        ],
        "output_node": schema.is_output_node,
        "function": "execute",
        "category": schema.category,
    }


class V3MigrationContractTests(unittest.TestCase):
    def test_required_g04_artifacts_exist(self):
        for path in (
            MIGRATION_CONTRACT_PATH,
            PROTOTYPE_WORKFLOWS_PATH,
            PROTOTYPE_PATH,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"required G04 artifact missing: {path.name}")

    def test_decision_and_two_tier_sources_are_pinned(self):
        contract = _load_json(MIGRATION_CONTRACT_PATH)

        self.assertEqual(1, contract["schema_version"])
        self.assertEqual("DEFER_PRODUCTION", contract["decision"])
        self.assertEqual("V1", contract["production_registration"])
        self.assertEqual("TextInput", contract["prototype_node"])
        self.assertIn("stable", contract["revisit_trigger"].lower())
        self.assertIn("v0_0_2", contract["revisit_trigger"])

        tiers = contract["supported_tiers"]
        self.assertEqual(["desktop_floor", "current_host"], [tier["id"] for tier in tiers])
        self.assertEqual(
            1,
            len({tier["v0_0_2_shim_blob_short"] for tier in tiers}),
            "the two tiers should pin the identical versioned shim",
        )
        self.assertEqual(
            2,
            len({tier["latest_io_blob_short"] for tier in tiers}),
            "the shim must be shown to delegate to different latest IO implementations",
        )
        for tier in tiers:
            self.assertFalse(tier["v0_0_2_stable"])
            self.assertEqual("V1_BEFORE_V3", tier["loader_precedence"])

    def test_classification_matches_all_registered_nodes(self):
        contract = _load_json(MIGRATION_CONTRACT_PATH)
        classifications = contract["nodes"]

        with PackageImportContext() as package:
            self.assertEqual(set(package.NODE_CLASS_MAPPINGS), set(classifications))

        self.assertEqual(18, len(classifications))
        counts = Counter()
        selected = []
        for node_id, entry in classifications.items():
            with self.subTest(node_id=node_id):
                self.assertIn(entry["classification"], ALLOWED_CLASSIFICATIONS)
                self.assertTrue(entry["rationale"].strip())
                self.assertTrue(entry["state_seams"])
                self.assertEqual(
                    entry["classification"] == "stateless",
                    entry["prototype_eligible"],
                )
                counts[entry["classification"]] += 1
                if entry.get("selected_prototype"):
                    selected.append(node_id)

        self.assertEqual(
            {
                "stateless": 8,
                "external_stateful": 4,
                "class_stateful": 2,
                "instance_stateful": 4,
            },
            dict(counts),
        )
        self.assertEqual(["TextInput"], selected)

    def test_required_stateful_seams_are_explicit(self):
        nodes = _load_json(MIGRATION_CONTRACT_PATH)["nodes"]

        expected_seams = {
            "AdvancedImageSaver": {
                "predictor_model_lifecycle",
                "predictor_preprocessor_lifecycle",
                "device_dtype_status",
            },
            "LoadImageBatch": {"incremental_class_state", "input_filesystem"},
            "TextStorageReader": {"storage_handler", "storage_version", "user_filesystem"},
            "TextStorageWriter": {"storage_handler", "storage_version", "user_filesystem"},
            "TP_SaveMask": {"constructor_output_directory", "output_filesystem"},
            "TextScraper": {"dns_resolution", "http_network"},
            "WildcardsNode": {"wildcard_filesystem", "seeded_randomness"},
            "AddTextToImage": {"font_registry", "font_filesystem"},
            "TP_LoadMask": {"input_filesystem"},
        }
        for node_id, required in expected_seams.items():
            with self.subTest(node_id=node_id):
                self.assertTrue(required.issubset(set(nodes[node_id]["state_seams"])))

    def test_prototype_is_test_only_and_has_no_forbidden_surfaces(self):
        prototype = _load_prototype_module()
        source = PROTOTYPE_PATH.read_text(encoding="utf-8")
        package_source = (PROJECT_ROOT / "__init__.py").read_text(encoding="utf-8")

        self.assertEqual("comfy_api.v0_0_2", prototype.PROTOTYPE_API_BINDING)
        self.assertFalse(prototype.PRODUCTION_ENABLED)
        self.assertEqual("TextInput", prototype.SELECTED_NODE_ID)
        self.assertNotIn("comfy_api.latest", source)
        self.assertNotIn("comfy_entrypoint", source)
        self.assertNotIn("auth_token", source.lower())
        self.assertNotIn("api_key", source.lower())
        self.assertNotIn("v3_text_input_prototype", package_source)
        self.assertNotIn("comfy_entrypoint", package_source)

        contract = _load_json(MIGRATION_CONTRACT_PATH)
        self.assertTrue(contract["registry_excludes_prototype"])

    def test_v1_v3_schema_and_special_method_parity_on_both_tiers(self):
        contract = _load_json(MIGRATION_CONTRACT_PATH)
        prototype_module = _load_prototype_module()

        with PackageImportContext() as package:
            v1_class = package.NODE_CLASS_MAPPINGS["TextInput"]
            v1_contract = _normalize_node_contract(v1_class)
            display_name = package.NODE_DISPLAY_NAME_MAPPINGS["TextInput"]

            for tier in contract["supported_tiers"]:
                with self.subTest(tier=tier["id"]):
                    prototype = prototype_module.build_text_input_v3_prototype(
                        _FakeIO(tier["id"])
                    )
                    schema = prototype.define_schema()
                    v3_contract = _normalize_v3_schema(schema)

                    self.assertEqual("TextInput", schema.node_id)
                    self.assertEqual(display_name, schema.display_name)
                    self.assertEqual(v1_class.DESCRIPTION, schema.description)
                    self.assertEqual(v1_class.SEARCH_ALIASES, schema.search_aliases)
                    self.assertEqual([], schema.hidden)
                    self.assertEqual("join_texts", v1_contract["function"])
                    self.assertEqual("execute", v3_contract["function"])
                    self.assertEqual(
                        {key: value for key, value in v1_contract.items() if key != "function"},
                        {key: value for key, value in v3_contract.items() if key != "function"},
                    )
                    self.assertNotIn("VALIDATE_INPUTS", v1_class.__dict__)
                    self.assertNotIn("validate_inputs", prototype.__dict__)
                    self.assertNotIn("IS_CHANGED", v1_class.__dict__)
                    self.assertNotIn("fingerprint_inputs", prototype.__dict__)

    def test_synthetic_workflow_execution_and_ui_parity_on_both_tiers(self):
        contract = _load_json(MIGRATION_CONTRACT_PATH)
        workflows = _load_json(PROTOTYPE_WORKFLOWS_PATH)
        prototype_module = _load_prototype_module()

        self.assertEqual(1, workflows["schema_version"])
        self.assertEqual("TextInput", workflows["node_type"])
        self.assertEqual("widgets_values", workflows["portable_baseline"])
        self.assertIsNone(FORBIDDEN_FIXTURE_TEXT.search(PROTOTYPE_WORKFLOWS_PATH.read_text(encoding="utf-8")))

        with PackageImportContext() as package:
            v1_class = package.NODE_CLASS_MAPPINGS["TextInput"]
            v1_contract = _normalize_node_contract(v1_class)
            widget_names = _widget_input_names(v1_contract)

            for tier in contract["supported_tiers"]:
                prototype = prototype_module.build_text_input_v3_prototype(_FakeIO(tier["id"]))
                for workflow in workflows["workflows"]:
                    with self.subTest(tier=tier["id"], workflow=workflow["id"]):
                        self.assertEqual(len(widget_names), len(workflow["widgets_values"]))
                        restored = dict(
                            zip(widget_names, workflow["widgets_values"], strict=True)
                        )
                        v1_result = v1_class().join_texts(**restored)
                        v3_output = prototype.execute(**restored)
                        expected = tuple(workflow["expected_result"])

                        self.assertEqual(expected, v1_result)
                        self.assertEqual(expected, v3_output.result)
                        self.assertIsNone(v3_output.ui)


if __name__ == "__main__":
    unittest.main()
