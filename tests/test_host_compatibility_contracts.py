import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image


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


if __name__ == "__main__":
    unittest.main()
