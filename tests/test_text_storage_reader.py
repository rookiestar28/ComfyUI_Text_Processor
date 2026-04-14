import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from text_storage import TextStorageHandler, TextStorageReader


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


if __name__ == "__main__":
    unittest.main()
