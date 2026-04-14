import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

import torch


if "folder_paths" not in sys.modules:
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths

from advanced_image_saver import AdvancedImageSaver


class AdvancedImageSaverPathTests(unittest.TestCase):
    def make_node(self, output_dir):
        node = AdvancedImageSaver()
        node.output_dir = str(output_dir)
        return node

    def test_relative_output_path_stays_under_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            node = self.make_node(output_dir)

            resolved = Path(node.resolve_output_folder("nested/results"))

            self.assertEqual(resolved, output_dir / "nested" / "results")

    def test_traversal_output_path_falls_back_to_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            node = self.make_node(output_dir)

            resolved = Path(node.resolve_output_folder("../escape"))

            self.assertEqual(resolved, output_dir.resolve())

    def test_absolute_output_path_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            absolute_target = Path(tmp) / "absolute"
            node = self.make_node(output_dir)

            blocked = Path(node.resolve_output_folder(str(absolute_target), allow_absolute_output_path=False))
            allowed = Path(node.resolve_output_folder(str(absolute_target), allow_absolute_output_path=True))

            self.assertEqual(blocked, output_dir.resolve())
            self.assertEqual(allowed, absolute_target.resolve())

    def test_filename_prefix_is_sanitized_as_single_filename_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            node = self.make_node(output_dir)

            self.assertEqual(node.sanitize_filename_prefix("../bad/name:01"), "_bad_name01")

    def test_save_images_sanitizes_prefix_before_writing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            node = self.make_node(output_dir)
            image = torch.zeros((1, 2, 2, 3), dtype=torch.float32)

            result = node.save_images(
                image,
                output_path=".",
                filename_prefix="../bad/name",
                show_previews="false",
                metadata_mode="none",
                extension="png",
            )

            output_files = result["result"][1]
            self.assertEqual(1, len(output_files))
            saved_path = Path(output_files[0])
            self.assertEqual(saved_path.parent, output_dir.resolve())
            self.assertIn("_bad_name", saved_path.name)


if __name__ == "__main__":
    unittest.main()
