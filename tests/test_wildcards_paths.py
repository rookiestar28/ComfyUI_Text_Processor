import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


if "folder_paths" not in sys.modules:
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.base_path = tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths

import wildcards


class WildcardsPathTests(unittest.TestCase):
    def write_wildcard(self, root, relative_name, content):
        path = Path(root) / (relative_name + ".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_get_all_wildcards_merges_comfyui_and_plugin_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            comfy_root = Path(tmp) / "comfy"
            plugin_root = Path(tmp) / "plugin" / "wildcards"
            self.write_wildcard(comfy_root / "wildcards", "root_only", "root")
            self.write_wildcard(plugin_root, "plugin_only", "plugin")
            self.write_wildcard(plugin_root, "nested/value", "nested")

            with patch.object(wildcards.folder_paths, "base_path", str(comfy_root), create=True):
                with patch.object(wildcards, "PLUGIN_WILDCARD_DIR", str(plugin_root)):
                    self.assertEqual(["nested/value", "plugin_only", "root_only"], wildcards.get_all_wildcards())

    def test_comfyui_root_takes_precedence_over_plugin_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            comfy_root = Path(tmp) / "comfy"
            plugin_root = Path(tmp) / "plugin" / "wildcards"
            self.write_wildcard(comfy_root / "wildcards", "style", "root-choice")
            self.write_wildcard(plugin_root, "style", "plugin-choice")

            with patch.object(wildcards.folder_paths, "base_path", str(comfy_root), create=True):
                with patch.object(wildcards, "PLUGIN_WILDCARD_DIR", str(plugin_root)):
                    output = wildcards.process_wildcard_syntax("__style__", seed=0)

            self.assertEqual("root-choice", output)

    def test_plugin_root_is_used_when_comfyui_root_has_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            comfy_root = Path(tmp) / "comfy"
            plugin_root = Path(tmp) / "plugin" / "wildcards"
            self.write_wildcard(plugin_root, "style", "plugin-choice")

            with patch.object(wildcards.folder_paths, "base_path", str(comfy_root), create=True):
                with patch.object(wildcards, "PLUGIN_WILDCARD_DIR", str(plugin_root)):
                    output = wildcards.process_wildcard_syntax("__style__", seed=0)

            self.assertEqual("plugin-choice", output)

    def test_nested_wildcard_paths_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            comfy_root = Path(tmp) / "comfy"
            plugin_root = Path(tmp) / "plugin" / "wildcards"
            self.write_wildcard(comfy_root / "wildcards", "nested/style", "nested-choice")

            with patch.object(wildcards.folder_paths, "base_path", str(comfy_root), create=True):
                with patch.object(wildcards, "PLUGIN_WILDCARD_DIR", str(plugin_root)):
                    output = wildcards.process_wildcard_syntax("__nested/style__", seed=0)

            self.assertEqual("nested-choice", output)

    def test_traversal_wildcard_name_is_left_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            comfy_root = Path(tmp) / "comfy"
            plugin_root = Path(tmp) / "plugin" / "wildcards"

            with patch.object(wildcards.folder_paths, "base_path", str(comfy_root), create=True):
                with patch.object(wildcards, "PLUGIN_WILDCARD_DIR", str(plugin_root)):
                    output = wildcards.process_wildcard_syntax("__../secret__", seed=0)

            self.assertEqual("__../secret__", output)


if __name__ == "__main__":
    unittest.main()
