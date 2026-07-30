import inspect
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from load_image_batch import LoadImageBatch


def _save_image(path: Path, color, mode="RGB", size=(2, 3)):
    image = Image.new(mode, size, color)
    image.save(path)
    return path


class LoadImageBatchTests(unittest.TestCase):
    def setUp(self):
        LoadImageBatch.clear_state()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.node = LoadImageBatch()

    def tearDown(self):
        self.tmp.cleanup()
        LoadImageBatch.clear_state()

    def test_single_image_loads_indexed_file_as_rgb_tensor_and_filename(self):
        _save_image(self.root / "b.png", (20, 30, 40))
        _save_image(self.root / "a.png", (100, 110, 120))

        image, filename = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            index=1,
            mode="single_image",
            allow_RGBA_output="false",
        )

        self.assertEqual(filename, "b.png")
        self.assertEqual(tuple(image.shape), (1, 3, 2, 3))
        self.assertEqual(image.dtype, torch.float32)
        self.assertAlmostEqual(float(image[0, 0, 0, 0]), 20 / 255.0)

    def test_windows_forward_slash_unicode_path_and_nested_pattern_load(self):
        nested = self.root / "中文 path" / "nested"
        nested.mkdir(parents=True)
        _save_image(nested / "sample.png", (11, 22, 33))

        image, filename = self.node.load_batch_images(
            path=nested.parent.as_posix(),
            pattern="nested/*.png",
            mode="single_image",
        )

        self.assertEqual(filename, "sample.png")
        self.assertEqual(tuple(image.shape), (1, 3, 2, 3))

    def test_filename_extension_can_be_removed(self):
        _save_image(self.root / "sample.png", (1, 2, 3))

        _image, filename = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="single_image",
            filename_text_extension="false",
        )

        self.assertEqual(filename, "sample")

    def test_rgba_output_can_be_preserved_or_converted_to_rgb(self):
        _save_image(self.root / "alpha.png", (1, 2, 3, 128), mode="RGBA")

        rgba, _ = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="single_image",
            allow_RGBA_output="true",
        )
        rgb, _ = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="single_image",
            allow_RGBA_output="false",
        )

        self.assertEqual(tuple(rgba.shape), (1, 3, 2, 4))
        self.assertEqual(tuple(rgb.shape), (1, 3, 2, 3))

    def test_incremental_mode_advances_by_label_and_resets_when_pattern_changes(self):
        _save_image(self.root / "a.png", (10, 0, 0))
        _save_image(self.root / "b.png", (20, 0, 0))
        _save_image(self.root / "c.jpg", (30, 0, 0))

        _first, first_name = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="incremental_image",
            label="batch-a",
        )
        _second, second_name = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="incremental_image",
            label="batch-a",
        )
        _reset, reset_name = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.jpg",
            mode="incremental_image",
            label="batch-a",
        )

        self.assertEqual((first_name, second_name, reset_name), ("a.png", "b.png", "c.jpg"))

    def test_random_mode_is_deterministic_for_seed(self):
        for name, color in [("a.png", (10, 0, 0)), ("b.png", (20, 0, 0)), ("c.png", (30, 0, 0))]:
            _save_image(self.root / name, color)

        _image_a, filename_a = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="random",
            seed=123,
        )
        _image_b, filename_b = self.node.load_batch_images(
            path=str(self.root),
            pattern="*.png",
            mode="random",
            seed=123,
        )

        self.assertEqual(filename_a, filename_b)

    def test_missing_path_empty_matches_and_invalid_index_raise_without_none_image(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.node.load_batch_images(path=str(self.root / "missing"), pattern="*.png")

        with self.assertRaisesRegex(ValueError, "No images found"):
            self.node.load_batch_images(path=str(self.root), pattern="*.png")

        _save_image(self.root / "a.png", (1, 2, 3))
        with self.assertRaisesRegex(ValueError, "Invalid image index"):
            self.node.load_batch_images(path=str(self.root), pattern="*.png", index=5)

    def test_pattern_cannot_escape_selected_directory(self):
        outside = self.root.parent / "outside.png"
        _save_image(outside, (200, 0, 0))

        with self.assertRaisesRegex(ValueError, "Unsafe image pattern"):
            self.node.load_batch_images(path=str(self.root), pattern="../outside.png")

    def test_invalid_image_file_raises_clear_error(self):
        bad_path = self.root / "bad.png"
        bad_path.write_text("not an image", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Failed to load image"):
            self.node.load_batch_images(path=str(self.root), pattern="*.png")

    def test_validate_inputs_accepts_valid_static_image_match(self):
        _save_image(self.root / "a.png", (1, 2, 3))

        result = LoadImageBatch.VALIDATE_INPUTS(
            path=str(self.root),
            pattern="*.png",
            index=0,
            mode="single_image",
        )

        self.assertTrue(result)

    def test_validate_inputs_delegates_unrequested_fields_to_host(self):
        input_types = LoadImageBatch.INPUT_TYPES()
        available_inputs = {
            input_name
            for group_name in ("required", "optional")
            for input_name in input_types.get(group_name, {})
        }
        parameters = inspect.signature(LoadImageBatch.VALIDATE_INPUTS).parameters
        has_var_keyword = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        explicit_inputs = {
            parameter.name
            for parameter in parameters.values()
            if parameter.kind is not inspect.Parameter.VAR_KEYWORD
        }
        custom_validated = (
            available_inputs
            if has_var_keyword
            else available_inputs & explicit_inputs
        )
        default_validated = available_inputs - custom_validated

        self.assertFalse(
            has_var_keyword,
            "VAR_KEYWORD claims every available input and bypasses ComfyUI default validation",
        )
        self.assertEqual({"path", "pattern", "index", "mode"}, custom_validated)
        self.assertEqual(
            {"seed", "label", "allow_RGBA_output", "filename_text_extension"},
            default_validated,
        )

    def test_validate_inputs_reports_missing_empty_unsafe_and_index_errors(self):
        missing = LoadImageBatch.VALIDATE_INPUTS(path=str(self.root / "missing"), pattern="*.png")
        self.assertIsInstance(missing, str)
        self.assertIn("does not exist", missing)

        empty = LoadImageBatch.VALIDATE_INPUTS(path=str(self.root), pattern="*.png")
        self.assertIsInstance(empty, str)
        self.assertIn("No images found", empty)

        unsafe = LoadImageBatch.VALIDATE_INPUTS(path=str(self.root), pattern="../*.png")
        self.assertIsInstance(unsafe, str)
        self.assertIn("Unsafe image pattern", unsafe)

        _save_image(self.root / "a.png", (1, 2, 3))
        invalid_index = LoadImageBatch.VALIDATE_INPUTS(
            path=str(self.root),
            pattern="*.png",
            index=5,
            mode="single_image",
        )
        self.assertIsInstance(invalid_index, str)
        self.assertIn("Invalid image index", invalid_index)

    def test_validate_inputs_does_not_advance_incremental_state(self):
        _save_image(self.root / "a.png", (1, 2, 3))
        _save_image(self.root / "b.png", (4, 5, 6))

        result = LoadImageBatch.VALIDATE_INPUTS(
            path=str(self.root),
            pattern="*.png",
            mode="incremental_image",
        )

        self.assertTrue(result)
        self.assertEqual({}, LoadImageBatch._incremental_state)


if __name__ == "__main__":
    unittest.main()
