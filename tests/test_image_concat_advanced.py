import unittest

import torch

from Image_concat_advanced import TP_ImageConcatenateMulti


def _image(value, height=2, width=2, channels=3):
    return torch.full((1, height, width, channels), float(value), dtype=torch.float32)


def _cell_value(output, row, col, height=2, width=2):
    y = row * height + height // 2
    x = col * width + width // 2
    return float(output[0, y, x, 0])


class ImageConcatAdvancedGridTests(unittest.TestCase):
    def setUp(self):
        self.node = TP_ImageConcatenateMulti()
        self.images = [_image(i) for i in range(1, 6)]

    def test_left_to_right_wraps_and_pads_final_row(self):
        output, = self.node.concatenate(self.images, "left_to_right", 3, "nearest", "rgb")

        self.assertEqual(tuple(output.shape), (1, 4, 6, 3))
        self.assertEqual([_cell_value(output, 0, c) for c in range(3)], [1.0, 2.0, 3.0])
        self.assertEqual([_cell_value(output, 1, c) for c in range(3)], [4.0, 5.0, 0.0])

    def test_right_to_left_wraps_and_pads_final_row(self):
        output, = self.node.concatenate(self.images, "right_to_left", 3, "nearest", "rgb")

        self.assertEqual(tuple(output.shape), (1, 4, 6, 3))
        self.assertEqual([_cell_value(output, 0, c) for c in range(3)], [3.0, 2.0, 1.0])
        self.assertEqual([_cell_value(output, 1, c) for c in range(3)], [0.0, 5.0, 4.0])

    def test_top_to_bottom_wraps_and_pads_final_column(self):
        output, = self.node.concatenate(self.images, "top_to_bottom", 3, "nearest", "rgb")

        self.assertEqual(tuple(output.shape), (1, 6, 4, 3))
        self.assertEqual([_cell_value(output, r, 0) for r in range(3)], [1.0, 2.0, 3.0])
        self.assertEqual([_cell_value(output, r, 1) for r in range(3)], [4.0, 5.0, 0.0])

    def test_bottom_to_top_wraps_and_pads_final_column(self):
        output, = self.node.concatenate(self.images, "bottom_to_top", 3, "nearest", "rgb")

        self.assertEqual(tuple(output.shape), (1, 6, 4, 3))
        self.assertEqual([_cell_value(output, r, 0) for r in range(3)], [3.0, 2.0, 1.0])
        self.assertEqual([_cell_value(output, r, 1) for r in range(3)], [0.0, 5.0, 4.0])

    def test_resizes_mismatched_resolution_to_first_image_cell(self):
        output, = self.node.concatenate(
            [_image(1, 2, 2, 3), _image(2, 4, 2, 3)],
            "left_to_right",
            2,
            "nearest",
            "rgb",
        )

        self.assertEqual(tuple(output.shape), (1, 2, 4, 3))

    def test_output_channel_modes_and_legacy_direction_values(self):
        direction_options = TP_ImageConcatenateMulti.INPUT_TYPES()["required"]["direction"][0]
        for legacy in ("right", "left", "down", "up"):
            self.assertIn(legacy, direction_options)

        output, = self.node.concatenate([_image(1, channels=3), _image(2, channels=4)], "right", 2, "nearest", "auto")
        self.assertEqual(output.shape[-1], 4)

        output, = self.node.concatenate([_image(1, channels=4)], "down", 1, "nearest", "rgb")
        self.assertEqual(output.shape[-1], 3)

        output, = self.node.concatenate([_image(1, channels=3)], "up", 1, "nearest", "rgba")
        self.assertEqual(output.shape[-1], 4)

    def test_invalid_empty_and_unknown_inputs_raise_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "No images provided"):
            self.node.concatenate([], "left_to_right", 2, "nearest", "rgb")

        with self.assertRaisesRegex(ValueError, "Unsupported images input type"):
            self.node.concatenate(object(), "left_to_right", 2, "nearest", "rgb")

        with self.assertRaisesRegex(ValueError, "Unknown direction"):
            self.node.concatenate([_image(1)], "diagonal", 2, "nearest", "rgb")

        with self.assertRaisesRegex(ValueError, "max_images_per_line"):
            self.node.concatenate([_image(1)], "left_to_right", 0, "nearest", "rgb")

    def test_mixed_channel_inputs_are_converted_deterministically(self):
        grayscale = _image(0.25, channels=1)
        rgb = _image(0.5, channels=3)
        rgba = torch.cat([_image(0.75, channels=3), torch.full((1, 2, 2, 1), 0.2)], dim=-1)

        rgb_output, = self.node.concatenate([grayscale, rgba], "left_to_right", 2, "nearest", "rgb")
        self.assertEqual(tuple(rgb_output.shape), (1, 2, 4, 3))
        self.assertTrue(torch.allclose(rgb_output[:, :, :2, :], torch.full((1, 2, 2, 3), 0.25)))
        self.assertTrue(torch.allclose(rgb_output[:, :, 2:, :], torch.full((1, 2, 2, 3), 0.75)))

        rgba_output, = self.node.concatenate([rgb], "left_to_right", 1, "nearest", "rgba")
        self.assertEqual(tuple(rgba_output.shape), (1, 2, 2, 4))
        self.assertTrue(torch.allclose(rgba_output[..., :3], torch.full((1, 2, 2, 3), 0.5)))
        self.assertTrue(torch.allclose(rgba_output[..., 3], torch.ones((1, 2, 2))))

        auto_output, = self.node.concatenate([grayscale, rgb, rgba], "left_to_right", 3, "nearest", "auto")
        self.assertEqual(tuple(auto_output.shape), (1, 2, 6, 4))
        self.assertTrue(torch.allclose(auto_output[:, :, :2, 3], torch.ones((1, 2, 2))))
        self.assertTrue(torch.allclose(auto_output[:, :, 2:4, 3], torch.ones((1, 2, 2))))
        self.assertTrue(torch.allclose(auto_output[:, :, 4:6, 3], torch.full((1, 2, 2), 0.2)))

    def test_grid_dimensions_follow_axis_and_first_image_cell_size(self):
        images = [
            _image(1, height=3, width=5, channels=3),
            _image(2, height=6, width=2, channels=3),
            _image(3, height=3, width=5, channels=3),
            _image(4, height=3, width=5, channels=3),
            _image(5, height=3, width=5, channels=3),
        ]

        horizontal, = self.node.concatenate(images, "left_to_right", 2, "nearest", "rgb")
        vertical, = self.node.concatenate(images, "top_to_bottom", 2, "nearest", "rgb")

        self.assertEqual(tuple(horizontal.shape), (1, 9, 10, 3))
        self.assertEqual(tuple(vertical.shape), (1, 6, 15, 3))


if __name__ == "__main__":
    unittest.main()
