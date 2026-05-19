import sys
import tempfile
import types
import unittest
from pathlib import Path

import torch


def _install_folder_paths_stub(tmp_path):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.base_path = str(tmp_path)
    folder_paths.get_output_directory = lambda: str(tmp_path / "output")
    folder_paths.get_input_directory = lambda: str(tmp_path / "input")
    folder_paths.get_filename_list = lambda _category: []
    folder_paths.get_annotated_filepath = lambda name: str(tmp_path / "input" / name)

    def get_save_image_path(filename_prefix, output_dir, _width, _height):
        return output_dir, filename_prefix, 1, "", filename_prefix

    folder_paths.get_save_image_path = get_save_image_path
    previous = sys.modules.get("folder_paths")
    sys.modules["folder_paths"] = folder_paths
    return previous


def _restore_folder_paths(previous):
    if previous is None:
        sys.modules.pop("folder_paths", None)
    else:
        sys.modules["folder_paths"] = previous


def _load_node_class(tmp_path):
    repo_dir = Path(__file__).resolve().parents[1]
    package_parent = repo_dir.parent
    previous_folder_paths = _install_folder_paths_stub(tmp_path)
    sys.path.insert(0, str(package_parent))
    try:
        sys.modules.pop("ComfyUI_Text_Processor.add_text_to_image", None)
        module = __import__(
            "ComfyUI_Text_Processor.add_text_to_image",
            fromlist=["AddTextToImage"],
        )
        return module.AddTextToImage, previous_folder_paths, package_parent
    except Exception:
        _restore_folder_paths(previous_folder_paths)
        try:
            sys.path.remove(str(package_parent))
        except ValueError:
            pass
        raise


class AddTextToImageRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.AddTextToImage, self.previous_folder_paths, self.package_parent = _load_node_class(self.tmp_path)
        self.node = self.AddTextToImage()

    def tearDown(self):
        _restore_folder_paths(self.previous_folder_paths)
        try:
            sys.path.remove(str(self.package_parent))
        except ValueError:
            pass
        self.tmp.cleanup()

    def test_empty_label_returns_original_image_tensor(self):
        image = torch.full((1, 4, 4, 3), 0.25, dtype=torch.float32)

        output, = self.node._execute_draw_on_batch_single(
            image=image,
            font_name=next(iter(self.AddTextToImage.fonts.keys())),
            text_position="bottom_center",
            background_mode="text_box",
            font_size=12,
            margin=1,
            line_spacing=1,
            text_color_hex="#ffffff",
            background_color_hex="#00000080",
            background_padding=1,
            auto_adapt=True,
            min_font_size=4,
            label_text="   ",
        )

        self.assertTrue(torch.equal(output, image))

    def test_unavailable_non_legacy_font_returns_original_image(self):
        image = torch.full((1, 4, 4, 3), 0.5, dtype=torch.float32)

        output, = self.node._execute_draw_on_batch_single(
            image=image,
            font_name="Definitely Missing Font",
            text_position="bottom_center",
            background_mode="text_box",
            font_size=12,
            margin=1,
            line_spacing=1,
            text_color_hex="#ffffff",
            background_color_hex="#00000080",
            background_padding=1,
            auto_adapt=True,
            min_font_size=4,
            label_text="caption",
        )

        self.assertTrue(torch.equal(output, image))

    def test_legacy_aileron_font_name_falls_back_to_available_font(self):
        image = torch.zeros((1, 16, 16, 3), dtype=torch.float32)

        output, = self.node._execute_draw_on_batch_single(
            image=image,
            font_name="Aileron_Regular",
            text_position="center_center",
            background_mode="text_box",
            font_size=10,
            margin=2,
            line_spacing=1,
            text_color_hex="#ffffff",
            background_color_hex="#000000ff",
            background_padding=1,
            auto_adapt=True,
            min_font_size=4,
            label_text="A",
        )

        self.assertEqual(tuple(output.shape), (1, 16, 16, 3))
        self.assertEqual(output.dtype, torch.float32)
        self.assertFalse(torch.equal(output, image))

    def test_cjk_and_long_token_wrapping_keeps_rgb_output_shape(self):
        image = torch.zeros((1, 24, 24, 3), dtype=torch.float32)
        font_name = next(iter(self.AddTextToImage.fonts.keys()))

        output, = self.node._execute_draw_on_batch_single(
            image=image,
            font_name=font_name,
            text_position="center_center",
            background_mode="full_width_strip",
            font_size=18,
            margin=1,
            line_spacing=1,
            text_color_hex="#ffffff",
            background_color_hex="#00000080",
            background_padding=1,
            auto_adapt=True,
            min_font_size=4,
            label_text="測試測試測試測試 Supercalifragilisticexpialidocious",
        )

        self.assertEqual(tuple(output.shape), (1, 24, 24, 3))
        self.assertEqual(output.dtype, torch.float32)
        self.assertTrue(torch.all(output >= 0.0))
        self.assertTrue(torch.all(output <= 1.0))

    def test_list_inputs_reuse_last_values_and_return_output_list(self):
        image_a = torch.zeros((1, 12, 12, 3), dtype=torch.float32)
        image_b = torch.ones((1, 12, 12, 3), dtype=torch.float32) * 0.1
        font_name = next(iter(self.AddTextToImage.fonts.keys()))

        outputs, = self.node.execute_draw_on_batch(
            image=[image_a, image_b],
            font_name=[font_name],
            text_position=["top_left"],
            background_mode=["text_box"],
            font_size=[8],
            margin=[1],
            line_spacing=[1],
            text_color_hex=["#ffffff"],
            background_color_hex=["#00000080"],
            background_padding=[1],
            auto_adapt=[True],
            min_font_size=[4],
            label_text=["one", "two"],
        )

        self.assertEqual(2, len(outputs))
        self.assertEqual(tuple(outputs[0].shape), (1, 12, 12, 3))
        self.assertEqual(tuple(outputs[1].shape), (1, 12, 12, 3))


if __name__ == "__main__":
    unittest.main()
