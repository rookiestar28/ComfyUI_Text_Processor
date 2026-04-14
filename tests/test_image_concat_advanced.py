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


if __name__ == "__main__":
    unittest.main()
