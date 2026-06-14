import unittest

import torch

from resize_image_advanced import ResizeImageAdvanced


def _solid_image(height, width, color):
    tensor = torch.zeros((1, height, width, 3), dtype=torch.float32)
    tensor[:, :, :, 0] = float(color[0])
    tensor[:, :, :, 1] = float(color[1])
    tensor[:, :, :, 2] = float(color[2])
    return tensor


def _split_image(height=2, width=4):
    image = torch.zeros((1, height, width, 3), dtype=torch.float32)
    image[:, :, : width // 2, 0] = 0.25
    image[:, :, width // 2 :, 0] = 0.75
    return image


class ResizeImageAdvancedTests(unittest.TestCase):
    def setUp(self):
        self.node = ResizeImageAdvanced()

    def resize(self, image, **overrides):
        kwargs = {
            "resize_mode": "explicit",
            "width": 4,
            "height": 4,
            "aspect_ratio": "original",
            "proportional_width": 1,
            "proportional_height": 1,
            "fit": "fill",
            "method": "nearest",
            "scale_to_side": "None",
            "scale_to_length": 4,
            "background_color": "#000000",
            "crop_position": "center",
            "round_to_multiple": "None",
            "device": "cpu",
        }
        kwargs.update(overrides)
        return self.node.resize(image=image, **kwargs)

    def test_input_types_expose_kj_and_layerstyle_controls(self):
        required = self.node.INPUT_TYPES()["required"]

        self.assertIn("resize_mode", required)
        self.assertIn("width", required)
        self.assertIn("height", required)
        self.assertIn("aspect_ratio", required)
        self.assertIn("scale_to_side", required)
        self.assertIn("scale_to_length", required)
        self.assertIn("background_color", required)
        self.assertIn("mask", self.node.INPUT_TYPES()["optional"])
        self.assertIn("letterbox", required["fit"][0])
        self.assertIn("crop", required["fit"][0])
        self.assertIn("fill", required["fit"][0])
        self.assertIn("resize", required["fit"][0])
        self.assertIn("pad", required["fit"][0])
        self.assertIn("pad_edge", required["fit"][0])
        self.assertIn("pad_edge_pixel", required["fit"][0])
        self.assertIn("pillarbox_blur", required["fit"][0])
        self.assertIn("total_pixels", required["fit"][0])
        self.assertIn("nearest-exact", required["method"][0])
        self.assertIn("nvidia_rtx_vsr", required["method"][0])
        self.assertIn("device", required)

    def test_explicit_resize_derives_zero_dimension_and_returns_empty_mask(self):
        image = _solid_image(2, 4, (0.5, 0.25, 0.0))

        output, width, height, mask = self.resize(image, width=8, height=0, fit="fill")

        self.assertEqual((width, height), (8, 4))
        self.assertEqual(tuple(output.shape), (1, 4, 8, 3))
        self.assertEqual(tuple(mask.shape), (1, 4, 8))
        self.assertTrue(torch.all(mask == 0.0))

    def test_resize_fit_preserves_aspect_without_padding(self):
        image = _solid_image(2, 4, (1.0, 0.0, 0.0))

        output, width, height, _mask = self.resize(image, width=4, height=4, fit="resize")

        self.assertEqual((width, height), (4, 2))
        self.assertEqual(tuple(output.shape), (1, 2, 4, 3))

    def test_aspect_ratio_mode_scales_to_presets_and_total_pixels(self):
        image = _solid_image(4, 6, (0.0, 0.0, 1.0))

        output, width, height, _mask = self.resize(
            image,
            resize_mode="aspect_ratio",
            aspect_ratio="16:9",
            scale_to_side="longest",
            scale_to_length=16,
            fit="fill",
        )

        self.assertEqual((width, height), (16, 9))
        self.assertEqual(tuple(output.shape), (1, 9, 16, 3))

        output, width, height, _mask = self.resize(
            image,
            resize_mode="aspect_ratio",
            aspect_ratio="1:1",
            scale_to_side="total_pixel(kilo pixel)",
            scale_to_length=1,
            fit="fill",
        )

        self.assertEqual((width, height), (31, 31))
        self.assertEqual(tuple(output.shape), (1, 31, 31, 3))

    def test_custom_aspect_ratio_and_round_to_multiple(self):
        image = _solid_image(3, 5, (0.2, 0.4, 0.6))

        output, width, height, _mask = self.resize(
            image,
            resize_mode="aspect_ratio",
            aspect_ratio="custom",
            proportional_width=3,
            proportional_height=2,
            scale_to_side="height",
            scale_to_length=7,
            round_to_multiple="4",
            fit="fill",
        )

        self.assertEqual((width, height), (12, 8))
        self.assertEqual(tuple(output.shape), (1, 8, 12, 3))

    def test_letterbox_uses_background_color_and_aligns_mask(self):
        image = _solid_image(2, 4, (1.0, 0.0, 0.0))
        mask = torch.ones((1, 2, 4), dtype=torch.float32)

        output, width, height, out_mask = self.resize(
            image,
            width=4,
            height=4,
            fit="letterbox",
            background_color="#00ff00",
            mask=mask,
        )

        self.assertEqual((width, height), (4, 4))
        self.assertEqual(tuple(output.shape), (1, 4, 4, 3))
        self.assertTrue(torch.allclose(output[:, 0, :, :], torch.tensor([0.0, 1.0, 0.0]).view(1, 1, 3)))
        self.assertTrue(torch.allclose(output[:, 1:3, :, :], torch.tensor([1.0, 0.0, 0.0]).view(1, 1, 1, 3)))
        self.assertTrue(torch.all(out_mask[:, 0, :] == 0.0))
        self.assertTrue(torch.all(out_mask[:, 1:3, :] == 1.0))
        self.assertTrue(torch.all(out_mask[:, 3, :] == 0.0))

    def test_crop_position_keeps_selected_edge_and_mask_alignment(self):
        image = _split_image()
        mask = torch.zeros((1, 2, 4), dtype=torch.float32)
        mask[:, :, 2:] = 1.0

        output, width, height, out_mask = self.resize(
            image,
            width=2,
            height=2,
            fit="crop",
            crop_position="right",
            mask=mask,
        )

        self.assertEqual((width, height), (2, 2))
        self.assertGreater(float(output[..., 0].mean()), 0.7)
        self.assertTrue(torch.all(out_mask == 1.0))

    def test_kj_pad_edge_pixel_and_total_pixels_modes_are_preserved(self):
        image = torch.zeros((1, 2, 4, 3), dtype=torch.float32)
        image[0, :, :, 0] = torch.tensor([[0.0, 0.33, 0.66, 1.0], [0.0, 0.33, 0.66, 1.0]])

        output, width, height, _mask = self.resize(
            image,
            width=4,
            height=4,
            fit="pad_edge_pixel",
            background_color="#00ff00",
        )

        self.assertEqual((width, height), (4, 4))
        self.assertTrue(torch.allclose(output[0, 0, :, 0], torch.tensor([0.0, 0.33, 0.66, 1.0]), atol=0.02))
        self.assertTrue(torch.all(output[0, 0, :, 1] == 0.0))

        output, width, height, _mask = self.resize(
            image,
            width=10,
            height=10,
            fit="total_pixels",
        )

        self.assertEqual((width, height), (14, 7))
        self.assertEqual(tuple(output.shape), (1, 7, 14, 3))

    def test_invalid_inputs_fail_clearly(self):
        image = _solid_image(2, 4, (0.0, 0.0, 0.0))

        with self.assertRaisesRegex(ValueError, "Invalid background_color"):
            self.resize(image, fit="letterbox", background_color="not-a-color")

        with self.assertRaisesRegex(ValueError, "custom aspect ratio"):
            self.resize(
                image,
                resize_mode="aspect_ratio",
                aspect_ratio="custom",
                proportional_width=0,
                proportional_height=1,
            )

        with self.assertRaisesRegex(ValueError, "expected IMAGE tensor"):
            self.resize(torch.zeros((2, 4, 3), dtype=torch.float32))

        with self.assertRaisesRegex(ValueError, "target dimensions"):
            self.resize(image, width=999999, height=999999)

    def test_nvidia_rtx_vsr_option_is_exposed_and_dependency_gated(self):
        image = _solid_image(2, 2, (0.0, 0.0, 1.0))

        with self.assertRaisesRegex((ImportError, RuntimeError), "NVIDIA RTX Video Super Resolution"):
            self.resize(image, width=4, height=4, method="nvidia_rtx_vsr", device="cpu")


if __name__ == "__main__":
    unittest.main()
