import copy
import importlib
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
NODE_CONTRACTS_PATH = FIXTURES_DIR / "node_contracts_v1.json"
LEGACY_WORKFLOWS_PATH = FIXTURES_DIR / "legacy_workflows_v1.json"
WIDGET_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN"}
FORBIDDEN_FIXTURE_TEXT = re.compile(
    r"(?i)(?:[A-Z]:\\|/home/|\.planning|reference/docs|api[_-]?key|authorization|cookie|secret|token)"
)


def _json_value(value):
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _normalize_inputs(input_types):
    normalized = {}
    for group_name in ("required", "optional", "hidden"):
        group = input_types.get(group_name, {})
        normalized_group = []
        for input_name, input_spec in group.items():
            if isinstance(input_spec, (tuple, list)):
                raw_type = input_spec[0]
                options = input_spec[1] if len(input_spec) > 1 and isinstance(input_spec[1], dict) else {}
            else:
                raw_type = input_spec
                options = {}

            is_combo = isinstance(raw_type, (tuple, list))
            input_type = "COMBO" if is_combo else str(raw_type)
            is_widget = not options.get("forceInput", False) and (
                is_combo or input_type in WIDGET_TYPES
            )
            normalized_group.append(
                {
                    "name": input_name,
                    "type": input_type,
                    "default": _json_value(options.get("default")),
                    "widget": is_widget,
                }
            )
        normalized[group_name] = normalized_group
    return normalized


def _normalize_node_contract(node_class):
    input_contract = _normalize_inputs(node_class.INPUT_TYPES())
    return_types = list(getattr(node_class, "RETURN_TYPES", ()))
    return_names = list(getattr(node_class, "RETURN_NAMES", return_types))
    if len(return_names) != len(return_types):
        raise AssertionError(f"{node_class.__name__} RETURN_NAMES length mismatch")

    return {
        **input_contract,
        "outputs": [
            {"index": index, "type": output_type, "name": return_names[index]}
            for index, output_type in enumerate(return_types)
        ],
        "output_node": bool(getattr(node_class, "OUTPUT_NODE", False)),
        "function": getattr(node_class, "FUNCTION", ""),
        "category": getattr(node_class, "CATEGORY", ""),
    }


def _normalized_package_contracts(package):
    return {
        node_id: _normalize_node_contract(node_class)
        for node_id, node_class in package.NODE_CLASS_MAPPINGS.items()
    }


def _widget_input_names(node_contract):
    return [
        item["name"]
        for group_name in ("required", "optional")
        for item in node_contract[group_name]
        if item["widget"]
    ]


class PackageImportContext:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.user_dir = self.root / "user"
        self.previous_folder_paths = None
        self.package_parent = Path(__file__).resolve().parents[2]

    def __enter__(self):
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        self.user_dir.mkdir()

        folder_paths = types.ModuleType("folder_paths")
        folder_paths.base_path = str(self.root)
        folder_paths.get_output_directory = lambda: str(self.output_dir)
        folder_paths.get_input_directory = lambda: str(self.input_dir)
        folder_paths.get_user_directory = lambda: str(self.user_dir)
        folder_paths.get_filename_list = lambda _category: []
        folder_paths.get_annotated_filepath = lambda name: str(self.input_dir / name)
        folder_paths.exists_annotated_filepath = lambda name: (self.input_dir / name).exists()

        def get_save_image_path(filename_prefix, _output_dir, _width, _height):
            return str(self.output_dir), filename_prefix, 1, "", filename_prefix

        folder_paths.get_save_image_path = get_save_image_path

        self.previous_folder_paths = sys.modules.get("folder_paths")
        sys.modules["folder_paths"] = folder_paths
        sys.path.insert(0, str(self.package_parent))
        sys.modules.pop("ComfyUI_Text_Processor", None)
        return importlib.import_module("ComfyUI_Text_Processor")

    def __exit__(self, _exc_type, _exc, _tb):
        try:
            sys.path.remove(str(self.package_parent))
        except ValueError:
            pass
        if self.previous_folder_paths is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = self.previous_folder_paths
        self.tmp.cleanup()


class HostCompatibilityContractTests(unittest.TestCase):
    def test_exported_nodes_have_host_object_info_metadata(self):
        with PackageImportContext() as package:
            for node_id, node_class in package.NODE_CLASS_MAPPINGS.items():
                input_info = node_class.INPUT_TYPES()
                input_order = {
                    key: list(value.keys())
                    for key, value in input_info.items()
                    if isinstance(value, dict)
                }
                info = {
                    "input": input_info,
                    "input_order": input_order,
                    "output": getattr(node_class, "RETURN_TYPES", ()),
                    "description": getattr(node_class, "DESCRIPTION", ""),
                    "search_aliases": getattr(node_class, "SEARCH_ALIASES", []),
                    "output_tooltips": getattr(node_class, "OUTPUT_TOOLTIPS", ()),
                }

                self.assertTrue(info["description"].strip(), node_id)
                self.assertTrue(info["search_aliases"], node_id)
                if info["output"]:
                    self.assertEqual(len(info["output"]), len(info["output_tooltips"]), node_id)

    def test_image_saver_preview_entries_are_contained_by_output_root(self):
        with PackageImportContext() as package:
            node = package.NODE_CLASS_MAPPINGS["AdvancedImageSaver"]()
            output_dir = Path(node.output_dir)
            inside = output_dir / "nested"
            outside = output_dir.parent / "external"

            inside_entry = node.build_preview_entry(str(inside), "image.png")
            outside_entry = node.build_preview_entry(str(outside), "image.png")

            self.assertEqual({"filename": "image.png", "subfolder": "nested", "type": "output"}, inside_entry)
            self.assertIsNone(outside_entry)

    def test_loader_validation_contracts_are_available(self):
        with PackageImportContext() as package:
            load_batch = package.NODE_CLASS_MAPPINGS["LoadImageBatch"]
            input_dir = Path(sys.modules["folder_paths"].get_input_directory())
            Image.new("RGB", (1, 1), (1, 2, 3)).save(input_dir / "sample.png")

            self.assertTrue(load_batch.VALIDATE_INPUTS(path=str(input_dir), pattern="*.png", index=0))
            unsafe = load_batch.VALIDATE_INPUTS(path=str(input_dir), pattern="../*.png")
            self.assertIsInstance(unsafe, str)
            self.assertIn("Unsafe image pattern", unsafe)

            load_mask = package.NODE_CLASS_MAPPINGS["TP_LoadMask"]
            self.assertTrue(load_mask.VALIDATE_INPUTS("sample.png"))
            invalid = load_mask.VALIDATE_INPUTS("missing.png")
            self.assertIsInstance(invalid, str)
            self.assertIn("Invalid mask image file", invalid)

    def test_text_storage_prefers_user_dir_and_reads_legacy_fallback(self):
        with PackageImportContext():
            text_storage = importlib.import_module("ComfyUI_Text_Processor.text_storage")
            root = Path(sys.modules["folder_paths"].get_user_directory()).parent
            legacy_dir = root / "legacy" / "text_storage"
            legacy_dir.mkdir(parents=True)
            with open(legacy_dir / "text_storage.json", "w", encoding="utf-8") as f:
                json.dump({"Legacy": "legacy value"}, f)

            with patch.object(text_storage, "PLUGIN_STORAGE_DIR", str(legacy_dir)):
                handler = text_storage.TextStorageHandler()
                handler.save_text("", "Preferred", "preferred value", "add", "json")

                self.assertEqual("legacy value", handler.read_content("Legacy"))
                self.assertEqual("preferred value", handler.read_content("Preferred"))
                self.assertIn("Legacy", handler.get_all_keys())
                self.assertIn("Preferred", handler.get_all_keys())

                preferred_json = Path(handler.storage_dir) / "text_storage.json"
                with open(preferred_json, "r", encoding="utf-8") as f:
                    self.assertIn("Preferred", json.load(f))


class WorkflowSerializationContractTests(unittest.TestCase):
    def load_contract_fixture(self):
        with open(NODE_CONTRACTS_PATH, encoding="utf-8") as fixture_file:
            manifest = json.load(fixture_file)
        self.assertEqual(1, manifest.get("schema_version"))
        self.assertIsInstance(manifest.get("nodes"), dict)
        return manifest

    def load_workflow_fixture(self):
        with open(LEGACY_WORKFLOWS_PATH, encoding="utf-8") as fixture_file:
            workflows = json.load(fixture_file)
        self.assertEqual(1, workflows.get("schema_version"))
        self.assertEqual("widgets_values", workflows.get("portable_baseline"))
        self.assertIsInstance(workflows.get("workflows"), list)
        return workflows

    def assert_contracts_match(self, expected, actual):
        self.assertEqual(expected, actual)

    def test_tracked_contract_and_legacy_workflow_fixtures_exist(self):
        self.assertTrue(
            NODE_CONTRACTS_PATH.is_file(),
            "tracked V1 node contract fixture is required",
        )
        self.assertTrue(
            LEGACY_WORKFLOWS_PATH.is_file(),
            "tracked synthetic legacy workflow fixture is required",
        )

    def test_manifest_matches_all_registered_v1_node_contracts(self):
        manifest = self.load_contract_fixture()
        self.assertEqual(1, manifest.get("schema_version"))
        self.assertIn("nodes", manifest)

        with PackageImportContext() as package:
            actual = _normalized_package_contracts(package)

        self.assertEqual(17, len(actual))
        self.assert_contracts_match(manifest["nodes"], actual)

    def test_contract_comparator_rejects_protected_drift(self):
        manifest = self.load_contract_fixture()
        expected = manifest["nodes"]

        with PackageImportContext() as package:
            actual = _normalized_package_contracts(package)

        mutations = {}

        reordered_input = copy.deepcopy(actual)
        reordered_input["AdvancedImageSaver"]["required"][1:3] = reversed(
            reordered_input["AdvancedImageSaver"]["required"][1:3]
        )
        mutations["input reorder"] = reordered_input

        renamed_input = copy.deepcopy(actual)
        renamed_input["LoadImageBatch"]["required"][0]["name"] = "renamed_path"
        mutations["input rename"] = renamed_input

        reordered_output = copy.deepcopy(actual)
        reordered_output["LoadImageBatch"]["outputs"].reverse()
        mutations["output reorder"] = reordered_output

        changed_output_type = copy.deepcopy(actual)
        changed_output_type["LoadImageBatch"]["outputs"][0]["type"] = "MASK"
        mutations["output type"] = changed_output_type

        changed_output_name = copy.deepcopy(actual)
        changed_output_name["LoadImageBatch"]["outputs"][0]["name"] = "renamed_image"
        mutations["output name"] = changed_output_name

        renamed_node = copy.deepcopy(actual)
        renamed_node["RenamedLoadImageBatch"] = renamed_node.pop("LoadImageBatch")
        mutations["node id"] = renamed_node

        for drift_name, mutated in mutations.items():
            with self.subTest(drift=drift_name):
                with self.assertRaises(AssertionError):
                    self.assert_contracts_match(expected, mutated)

    def test_synthetic_legacy_workflows_restore_positional_widgets(self):
        manifest = self.load_contract_fixture()
        workflows = self.load_workflow_fixture()

        self.assertEqual(1, workflows.get("schema_version"))
        self.assertEqual("widgets_values", workflows.get("portable_baseline"))

        required_node_types = {
            "AdvancedImageSaver",
            "TP_SaveMask",
            "TP_LoadMask",
            "TextStorageReader",
            "TextStorageWriter",
        }
        fixture_node_types = {fixture["node_type"] for fixture in workflows["workflows"]}
        self.assertTrue(required_node_types.issubset(fixture_node_types))

        for fixture in workflows["workflows"]:
            with self.subTest(fixture=fixture["id"]):
                node_contract = manifest["nodes"][fixture["node_type"]]
                widget_names = _widget_input_names(node_contract)
                self.assertEqual(len(widget_names), len(fixture["widgets_values"]))
                restored = dict(zip(widget_names, fixture["widgets_values"], strict=True))
                self.assertEqual(fixture["expected"], restored)

                named_values = fixture.get("widgets_values_named")
                if named_values is not None:
                    self.assertEqual(fixture["expected"], named_values)

    def test_workflow_fixtures_are_synthetic_and_content_free(self):
        fixture_text = LEGACY_WORKFLOWS_PATH.read_text(encoding="utf-8")
        self.assertIsNone(FORBIDDEN_FIXTURE_TEXT.search(fixture_text))

        workflows = self.load_workflow_fixture()
        for fixture in workflows["workflows"]:
            self.assertRegex(fixture["id"], r"^[a-z0-9_]+$")
            self.assertNotIn("prompt", fixture)
            self.assertNotIn("extra", fixture)
            self.assertNotIn("workflow", fixture)


if __name__ == "__main__":
    unittest.main()
