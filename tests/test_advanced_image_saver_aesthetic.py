import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch
from PIL import Image


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

    def test_failed_device_move_does_not_leave_half_initialized_predictor(self):
        node = AdvancedImageSaver()
        model = Mock()
        model.to.side_effect = RuntimeError("simulated cuda move failure")
        preprocessor = Mock()

        with patch.object(advanced_image_saver, "AESTHETIC_AVAILABLE", True):
            with patch.object(advanced_image_saver, "convert_v2_5_from_siglip", return_value=(model, preprocessor)):
                with patch.object(advanced_image_saver.torch.cuda, "is_available", return_value=True):
                    loaded = node.load_predictor(allow_remote_code=True)

        self.assertFalse(loaded)
        self.assertIsNone(node.predictor_model)
        self.assertIsNone(node.predictor_preprocessor)

    def test_input_types_expose_precision_and_lifecycle_controls(self):
        required = AdvancedImageSaver.INPUT_TYPES()["required"]

        self.assertIn("aesthetic_precision", required)
        self.assertIn("keep_aesthetic_model_loaded", required)
        self.assertIn("fp16", required["aesthetic_precision"][0])
        self.assertIn("auto", required["aesthetic_precision"][0])

    def test_bf16_setup_failure_falls_back_to_fp16(self):
        node = AdvancedImageSaver()
        model = Mock()
        model.to.side_effect = [RuntimeError("bf16 failed"), model]
        preprocessor = Mock()

        with patch.object(advanced_image_saver, "AESTHETIC_AVAILABLE", True):
            with patch.object(advanced_image_saver, "convert_v2_5_from_siglip", return_value=(model, preprocessor)):
                with patch.object(advanced_image_saver.torch.cuda, "is_available", return_value=True):
                    with patch.object(advanced_image_saver.torch.cuda, "is_bf16_supported", return_value=True):
                        loaded = node.load_predictor(allow_remote_code=True, aesthetic_precision="auto")

        self.assertTrue(loaded)
        self.assertIs(node.predictor_model, model)
        self.assertIs(node.predictor_preprocessor, preprocessor)
        self.assertEqual("ready", node.aesthetic_status)
        self.assertIn("float16", node.aesthetic_dtype)
        self.assertEqual(2, model.to.call_count)

    def test_keep_aesthetic_model_loaded_false_clears_predictor_after_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = self.make_node(Path(tmp) / "output")
            node.predictor_model = object()
            node.predictor_preprocessor = object()
            node.aesthetic_status = "ready"
            node.get_aesthetic_score = Mock(return_value=9.0)

            result = node.save_images(
                torch.zeros((1, 2, 2, 3), dtype=torch.float32),
                output_path=".",
                filename_prefix="clear_predictor",
                show_previews="false",
                metadata_mode="none",
                calculate_aesthetic_score="true",
                allow_aesthetic_remote_code="true",
                keep_aesthetic_model_loaded="false",
            )

        self.assertEqual(["9.0000"], result["result"][2])
        self.assertIsNone(node.predictor_model)
        self.assertIsNone(node.predictor_preprocessor)
        self.assertEqual("unloaded", node.aesthetic_status)

    def test_external_multiline_aesthetic_scores_apply_per_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = self.make_node(Path(tmp) / "output")
            images = torch.zeros((2, 2, 2, 3), dtype=torch.float32)

            result = node.save_images(
                images,
                output_path=".",
                filename_prefix="external_scores",
                show_previews="false",
                metadata_mode="none",
                aesthetic_threshold=0.0,
                aesthetic_score="7.125\n8.25",
            )

        self.assertEqual(["7.1250", "8.2500"], result["result"][2])
        self.assertEqual(2, len(result["result"][1]))

    def test_image_tensor_normalization_accepts_singleton_batch_and_float16(self):
        node = AdvancedImageSaver()
        image = torch.tensor(
            [[[[float("nan")], [1.5]], [[-0.5], [0.5]]]],
            dtype=torch.float16,
        )

        pil_image = node._aesthetic_tensor_to_pil(image)

        self.assertIsInstance(pil_image, Image.Image)
        self.assertEqual("RGB", pil_image.mode)
        self.assertEqual((2, 2), pil_image.size)

    def test_prediction_failure_returns_diagnostic_instead_of_numeric_low_score(self):
        node = AdvancedImageSaver()
        node.predictor_model = Mock(side_effect=RuntimeError("simulated inference failure"))
        node.predictor_preprocessor = Mock()
        node.predictor_preprocessor.return_value.pixel_values = torch.zeros((1, 3, 2, 2))

        score = node.get_aesthetic_score(torch.zeros((2, 2, 3), dtype=torch.float32))

        self.assertIsNone(score.value)
        self.assertIn("simulated inference failure", score.error)


if __name__ == "__main__":
    unittest.main()
