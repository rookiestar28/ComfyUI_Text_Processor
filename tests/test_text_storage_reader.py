import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import text_storage
from text_storage import TextStorageHandler, TextStorageReader


class FolderPathsStub:
    def __init__(self, user_dir):
        self.module = types.ModuleType("folder_paths")
        self.module.get_user_directory = lambda: str(user_dir)
        self.previous = None

    def __enter__(self):
        self.previous = sys.modules.get("folder_paths")
        sys.modules["folder_paths"] = self.module
        return self.module

    def __exit__(self, _exc_type, _exc, _tb):
        if self.previous is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = self.previous


class TextStorageReaderTests(unittest.TestCase):
    def test_input_types_returns_placeholder_when_storage_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = Path(tmp)

            def fake_init(self):
                self.storage_dir = str(storage_dir)
                self.json_file = str(storage_dir / "text_storage.json")
                self._ensure_storage_exists()

            with patch.object(TextStorageHandler, "__init__", fake_init):
                input_types = TextStorageReader.INPUT_TYPES()

            self.assertEqual(["No texts saved yet"], list(input_types["required"]["text_key"][0]))

    def test_reader_returns_empty_string_for_placeholder(self):
        reader = TextStorageReader()
        self.assertEqual(("",), reader.read_text("No texts saved yet"))

    def test_input_types_lists_real_saved_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = Path(tmp)

            def fake_init(self):
                self.storage_dir = str(storage_dir)
                self.json_file = str(storage_dir / "text_storage.json")
                self._ensure_storage_exists()

            with patch.object(TextStorageHandler, "__init__", fake_init):
                handler = TextStorageHandler()
                handler.save_text("", "Example", "hello", "add", "json")
                input_types = TextStorageReader.INPUT_TYPES()

            self.assertEqual(["Example"], list(input_types["required"]["text_key"][0]))

    def test_handler_prefers_comfyui_user_directory_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "user"
            legacy_dir = root / "legacy" / "text_storage"

            with FolderPathsStub(user_dir), patch.object(text_storage, "PLUGIN_STORAGE_DIR", str(legacy_dir)):
                handler = TextStorageHandler()
                handler.save_text("", "UserKey", "preferred", "add", "json")

            expected_dir = user_dir / "ComfyUI_Text_Processor" / "text_storage"
            self.assertEqual(expected_dir.resolve(), Path(handler.storage_dir).resolve())
            self.assertEqual(legacy_dir.resolve(), Path(handler.legacy_storage_dir).resolve())
            with open(expected_dir / "text_storage.json", "r", encoding="utf-8") as f:
                self.assertEqual({"UserKey": "preferred"}, json.load(f))

    def test_reader_lists_and_reads_legacy_entries_when_user_directory_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "user"
            legacy_dir = root / "legacy" / "text_storage"
            legacy_dir.mkdir(parents=True)
            with open(legacy_dir / "text_storage.json", "w", encoding="utf-8") as f:
                json.dump({"LegacyKey": "legacy value"}, f)

            with FolderPathsStub(user_dir), patch.object(text_storage, "PLUGIN_STORAGE_DIR", str(legacy_dir)):
                handler = TextStorageHandler()

                self.assertIn("LegacyKey", handler.get_all_keys())
                self.assertEqual("legacy value", handler.read_content("LegacyKey"))

    def test_delete_removes_matching_entries_from_preferred_and_legacy_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "user"
            legacy_dir = root / "legacy" / "text_storage"
            preferred_dir = user_dir / "ComfyUI_Text_Processor" / "text_storage"
            legacy_dir.mkdir(parents=True)
            preferred_dir.mkdir(parents=True)

            for storage_dir, value in [(legacy_dir, "legacy"), (preferred_dir, "preferred")]:
                with open(storage_dir / "text_storage.json", "w", encoding="utf-8") as f:
                    json.dump({"DeleteMe": value}, f)
                (storage_dir / "DeleteMe.txt").write_text(value, encoding="utf-8")

            with FolderPathsStub(user_dir), patch.object(text_storage, "PLUGIN_STORAGE_DIR", str(legacy_dir)):
                handler = TextStorageHandler()
                handler.save_text("", "DeleteMe", "", "delete", "json")

            for storage_dir in [legacy_dir, preferred_dir]:
                with open(storage_dir / "text_storage.json", "r", encoding="utf-8") as f:
                    self.assertNotIn("DeleteMe", json.load(f))
                self.assertFalse((storage_dir / "DeleteMe.txt").exists())


if __name__ == "__main__":
    unittest.main()
