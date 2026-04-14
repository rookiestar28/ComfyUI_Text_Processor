import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch


if "folder_paths" not in sys.modules:
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths

import advanced_image_saver
from advanced_image_saver import AdvancedImageSaver


class AdvancedImageSaverAestheticTests(unittest.TestCase):
    def make_node(self, output_dir):
        node = AdvancedImageSaver()
        node.output_dir = str(output_dir)
        return node

    def test_calculate_score_without_remote_code_opt_in_does_not_load_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = self.make_node(Path(tmp) / "output")
            image = torch.zeros((1, 2, 2, 3), dtype=torch.float32)
            node.load_predictor = Mock(return_value=True)

            result = node.save_images(
                image,
                output_path=".",
                filename_prefix="aesthetic_gate",
                show_previews="false",
                metadata_mode="none",
                calculate_aesthetic_score="true",
                allow_aesthetic_remote_code="false",
            )

        node.load_predictor.assert_not_called()
        self.assertEqual(["N/A"], result["result"][2])

    def test_load_predictor_requires_remote_code_opt_in(self):
        node = AdvancedImageSaver()

        with patch.object(advanced_image_saver, "AESTHETIC_AVAILABLE", True):
            with patch.object(advanced_image_saver, "convert_v2_5_from_siglip") as converter:
                loaded = node.load_predictor(allow_remote_code=False)

        self.assertFalse(loaded)
        converter.assert_not_called()

    def test_load_predictor_passes_trust_remote_code_when_allowed(self):
        node = AdvancedImageSaver()
        model = Mock()
        preprocessor = Mock()

        with patch.object(advanced_image_saver, "AESTHETIC_AVAILABLE", True):
            with patch.object(advanced_image_saver, "convert_v2_5_from_siglip", return_value=(model, preprocessor)) as converter:
                with patch.object(advanced_image_saver.torch.cuda, "is_available", return_value=False):
                    loaded = node.load_predictor(allow_remote_code=True)

        self.assertTrue(loaded)
        converter.assert_called_once_with(low_cpu_mem_usage=True, trust_remote_code=True)


if __name__ == "__main__":
    unittest.main()
