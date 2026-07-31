import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


EXPECTED_NODE_IDS = {
    "AdvancedTextFilter",
    "TextInput",
    "TextScraper",
    "WildcardsNode",
    "AddTextToImage",
    "EvaluateInts",
    "EvaluateFloats",
    "EvaluateStrs",
    "AdvancedImageSaver",
    "TextStorageReader",
    "TextStorageWriter",
    "ImageCropper",
    "TP_SaveMask",
    "TP_LoadMask",
    "image_concat_advanced",
    "LoadImageBatch",
    "ResizeImageAdvanced",
    "Global_RandomSeed",
}


class NodeRegistrationTests(unittest.TestCase):
    def test_package_exports_expected_node_mappings(self):
        repo_dir = Path(__file__).resolve().parents[1]
        package_parent = repo_dir.parent

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            folder_paths = types.ModuleType("folder_paths")
            folder_paths.base_path = str(tmp_path)
            folder_paths.get_output_directory = lambda: str(tmp_path / "output")
            folder_paths.get_input_directory = lambda: str(tmp_path / "input")
            folder_paths.get_filename_list = lambda _category: []
            folder_paths.get_annotated_filepath = lambda name: str(tmp_path / "input" / name)

            def get_save_image_path(filename_prefix, output_dir, _width, _height):
                return output_dir, filename_prefix, 1, "", filename_prefix

            folder_paths.get_save_image_path = get_save_image_path

            previous_folder_paths = sys.modules.get("folder_paths")
            sys.modules["folder_paths"] = folder_paths
            sys.path.insert(0, str(package_parent))
            try:
                sys.modules.pop("ComfyUI_Text_Processor", None)
                module = importlib.import_module("ComfyUI_Text_Processor")
            finally:
                try:
                    sys.path.remove(str(package_parent))
                except ValueError:
                    pass
                if previous_folder_paths is None:
                    sys.modules.pop("folder_paths", None)
                else:
                    sys.modules["folder_paths"] = previous_folder_paths

            self.assertEqual(EXPECTED_NODE_IDS, set(module.NODE_CLASS_MAPPINGS))
            self.assertEqual(EXPECTED_NODE_IDS, set(module.NODE_DISPLAY_NAME_MAPPINGS))
            self.assertEqual("Load Image Batch", module.NODE_DISPLAY_NAME_MAPPINGS["LoadImageBatch"])
            self.assertEqual("Resize Image Advanced", module.NODE_DISPLAY_NAME_MAPPINGS["ResizeImageAdvanced"])
            for node_id, node_class in module.NODE_CLASS_MAPPINGS.items():
                self.assertTrue(callable(node_class), node_id)
                self.assertTrue(
                    node_class.CATEGORY == "ComfyUI Text Processor"
                    or node_class.CATEGORY.startswith("ComfyUI Text Processor/"),
                    f"{node_id} has unexpected category {node_class.CATEGORY!r}",
                )

            for node_id, node_class in module.NODE_CLASS_MAPPINGS.items():
                description = getattr(node_class, "DESCRIPTION", "")
                self.assertIsInstance(description, str, f"{node_id} DESCRIPTION must be a string")
                self.assertTrue(description.strip(), f"{node_id} missing DESCRIPTION")

                aliases = getattr(node_class, "SEARCH_ALIASES", [])
                self.assertIsInstance(aliases, (list, tuple), f"{node_id} SEARCH_ALIASES must be a list or tuple")
                self.assertTrue(aliases, f"{node_id} missing SEARCH_ALIASES")
                self.assertTrue(
                    all(isinstance(alias, str) and alias.strip() for alias in aliases),
                    f"{node_id} SEARCH_ALIASES must contain non-empty strings",
                )

                return_types = getattr(node_class, "RETURN_TYPES", ())
                if return_types:
                    tooltips = getattr(node_class, "OUTPUT_TOOLTIPS", ())
                    self.assertEqual(
                        len(return_types),
                        len(tooltips),
                        f"{node_id} OUTPUT_TOOLTIPS must match RETURN_TYPES length",
                    )
                    self.assertTrue(
                        all(isinstance(tooltip, str) and tooltip.strip() for tooltip in tooltips),
                        f"{node_id} OUTPUT_TOOLTIPS must contain non-empty strings",
                    )


if __name__ == "__main__":
    unittest.main()
