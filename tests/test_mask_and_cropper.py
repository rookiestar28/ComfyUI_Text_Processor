import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image


def _install_folder_paths_stub(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    folder_paths = types.ModuleType("folder_paths")
    folder_paths.base_path = str(tmp_path)
    folder_paths.get_output_directory = lambda: str(output_dir)
    folder_paths.get_input_directory = lambda: str(input_dir)
    folder_paths.get_filename_list = lambda _category: []
    folder_paths.get_annotated_filepath = lambda name: str(input_dir / name)

    def get_save_image_path(filename_prefix, _output_dir, _width, _height):
        return str(output_dir), filename_prefix, 1, "", filename_prefix

    folder_paths.get_save_image_path = get_save_image_path
    previous = sys.modules.get("folder_paths")
    sys.modules["folder_paths"] = folder_paths
    return previous, input_dir, output_dir


def _restore_folder_paths(previous):
    if previous is None:
        sys.modules.pop("folder_paths", None)
    else:
        sys.modules["folder_paths"] = previous


class MaskNodeBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.previous_folder_paths, self.input_dir, self.output_dir = _install_folder_paths_stub(self.tmp_path)
        sys.modules.pop("mask_nodes", None)
        self.mask_nodes = importlib.import_module("mask_nodes")

    def tearDown(self):
        sys.modules.pop("mask_nodes", None)
        _restore_folder_paths(self.previous_folder_paths)
        self.tmp.cleanup()

    def test_save_mask_writes_png_to_isolated_output_directory(self):
        mask = torch.tensor([[[0.0, 0.5], [1.0, 0.25]]], dtype=torch.float32)
        node = self.mask_nodes.TP_SaveMask()

        result = node.save_mask(mask, filename_prefix="unit_mask")

        files = sorted(self.output_dir.glob("unit_mask_*.png"))
        self.assertEqual(1, len(files))
        with Image.open(files[0]) as saved:
            self.assertEqual(saved.mode, "L")
            self.assertEqual(saved.size, (2, 2))
            self.assertEqual(np.array(saved).max(), 255)
        self.assertEqual("unit_mask_00001_.png", result["ui"]["images"][0]["filename"])

    def test_load_mask_returns_single_batch_float_mask_in_zero_to_one_range(self):
        image = Image.fromarray(np.array([[0, 128], [255, 64]], dtype=np.uint8), mode="L")
        image.save(self.input_dir / "mask.png")
        node = self.mask_nodes.TP_LoadMask()

        mask, = node.load_mask("mask.png")

        self.assertEqual(tuple(mask.shape), (1, 2, 2))
        self.assertEqual(mask.dtype, torch.float32)
        self.assertGreaterEqual(float(mask.min()), 0.0)
        self.assertLessEqual(float(mask.max()), 1.0)
        self.assertAlmostEqual(float(mask[0, 1, 0]), 1.0)

    def test_load_mask_input_types_prefers_comfyui_content_type_filter(self):
        folder_paths = sys.modules["folder_paths"]
        calls = []
        folder_paths.get_filename_list = lambda _category: ["mask.png", "notes.txt", "photo.webp"]

        def filter_files_content_types(files, content_types):
            calls.append((list(files), list(content_types)))
            return [file for file in files if file.endswith((".png", ".webp"))]

        folder_paths.filter_files_content_types = filter_files_content_types

        input_types = self.mask_nodes.TP_LoadMask.INPUT_TYPES()

        self.assertEqual([(["mask.png", "notes.txt", "photo.webp"], ["image"])], calls)
        self.assertEqual(["mask.png", "photo.webp"], input_types["required"]["image"][0])

    def test_load_mask_input_types_filters_extensions_when_content_type_helper_is_missing(self):
        folder_paths = sys.modules["folder_paths"]
        folder_paths.get_filename_list = lambda _category: ["mask.png", "notes.txt", "photo.webp"]

        input_types = self.mask_nodes.TP_LoadMask.INPUT_TYPES()

        self.assertEqual(["mask.png", "photo.webp"], input_types["required"]["image"][0])

    def test_load_mask_input_types_keeps_recursive_extension_fallback(self):
        folder_paths = sys.modules["folder_paths"]
        folder_paths.get_filename_list = lambda _category: (_ for _ in ()).throw(AttributeError("missing"))
        nested = self.input_dir / "nested"
        nested.mkdir()
        Image.new("RGB", (1, 1), (1, 2, 3)).save(nested / "mask.png")
        (nested / "notes.txt").write_text("not an image", encoding="utf-8")

        input_types = self.mask_nodes.TP_LoadMask.INPUT_TYPES()

        self.assertEqual(["nested/mask.png"], input_types["required"]["image"][0])

    def test_load_mask_validate_inputs_uses_host_existence_helper(self):
        folder_paths = sys.modules["folder_paths"]
        checked = []

        def exists_annotated_filepath(name):
            checked.append(name)
            return name == "mask.png"

        folder_paths.exists_annotated_filepath = exists_annotated_filepath

        self.assertTrue(self.mask_nodes.TP_LoadMask.VALIDATE_INPUTS("mask.png"))
        invalid = self.mask_nodes.TP_LoadMask.VALIDATE_INPUTS("missing.png")
        self.assertIsInstance(invalid, str)
        self.assertIn("Invalid mask image file", invalid)
        self.assertEqual(["mask.png", "missing.png"], checked)


class ImageCropperBehaviorTests(unittest.TestCase):
    def setUp(self):
        import image_cropper

        self.image_cropper = image_cropper
        self.node = image_cropper.NODE_CLASS_MAPPINGS["ImageCropper"]()

    def test_center_square_crop_preserves_selected_content(self):
        image = torch.zeros((1, 4, 6, 3), dtype=torch.float32)
        image[:, :, :1, 0] = 1.0
        image[:, :, 5:, 1] = 1.0

        output, = self.node.execute(
            image=image,
            enable_fixed_crop=False,
            fixed_crop_side="shortest",
            fixed_crop_length=4,
            aspect_ratio="1:1",
            proportional_width=1,
            proportional_height=1,
            alignment="center",
            offset_x=0,
            offset_y=0,
            scale_to_side="None",
            scale_to_length=4,
            interpolation_mode="nearest",
        )

        self.assertEqual(tuple(output.shape), (1, 4, 4, 3))
        self.assertTrue(torch.all(output[..., 0] == 0.0))
        self.assertTrue(torch.all(output[..., 1] == 0.0))

    def test_crop_then_scale_to_width_updates_dimensions(self):
        image = torch.zeros((1, 4, 6, 3), dtype=torch.float32)

        output, = self.node.execute(
            image=image,
            enable_fixed_crop=False,
            fixed_crop_side="shortest",
            fixed_crop_length=4,
            aspect_ratio="1:1",
            proportional_width=1,
            proportional_height=1,
            alignment="center",
            offset_x=0,
            offset_y=0,
            scale_to_side="width",
            scale_to_length=8,
            interpolation_mode="nearest",
        )

        self.assertEqual(tuple(output.shape), (1, 8, 8, 3))

    def test_mask_center_can_shift_center_crop(self):
        image = torch.zeros((1, 16, 24, 3), dtype=torch.float32)
        image[:, :, 0:12, 0] = 0.25
        image[:, :, 12:24, 0] = 0.75
        mask = torch.zeros((1, 16, 24), dtype=torch.float32)
        mask[:, :, 19:24] = 1.0

        unmasked, = self.node.execute(
            image=image,
            enable_fixed_crop=False,
            fixed_crop_side="shortest",
            fixed_crop_length=16,
            aspect_ratio="1:1",
            proportional_width=1,
            proportional_height=1,
            alignment="center",
            offset_x=0,
            offset_y=0,
            scale_to_side="None",
            scale_to_length=16,
            interpolation_mode="nearest",
        )
        masked, = self.node.execute(
            image=image,
            enable_fixed_crop=False,
            fixed_crop_side="shortest",
            fixed_crop_length=16,
            aspect_ratio="1:1",
            proportional_width=1,
            proportional_height=1,
            alignment="center",
            offset_x=0,
            offset_y=0,
            scale_to_side="None",
            scale_to_length=16,
            interpolation_mode="nearest",
            mask=mask,
        )

        self.assertEqual(tuple(masked.shape), (1, 16, 16, 3))
        self.assertGreater(float(masked[..., 0].mean()), float(unmasked[..., 0].mean()))


if __name__ == "__main__":
    unittest.main()
