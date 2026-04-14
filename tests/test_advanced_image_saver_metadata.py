import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import torch
from PIL import Image


if "folder_paths" not in sys.modules:
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths

from advanced_image_saver import AdvancedImageSaver


PROMPT = {
    "1": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "positive prompt"},
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "negative prompt"},
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "steps": 20,
            "cfg": 7.5,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 123,
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "model.safetensors"},
    },
    "5": {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "vae.safetensors"},
    },
    "6": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 64, "height": 32},
    },
}

EXTRA_PNGINFO = {
    "workflow": {"nodes": [{"id": 1, "type": "KSampler"}]},
    "custom": {"project": "metadata-test"},
}


class AdvancedImageSaverMetadataTests(unittest.TestCase):
    def make_node(self, output_dir):
        node = AdvancedImageSaver()
        node.output_dir = str(output_dir)
        return node

    def save_image(self, extension, metadata_mode, embed_workflow):
        tmp = tempfile.TemporaryDirectory()
        output_dir = Path(tmp.name) / "output"
        node = self.make_node(output_dir)
        image = torch.zeros((1, 2, 2, 3), dtype=torch.float32)

        result = node.save_images(
            image,
            output_path=".",
            filename_prefix=f"metadata_{extension}_{metadata_mode}_{embed_workflow}",
            show_previews="false",
            metadata_mode=metadata_mode,
            embed_workflow=embed_workflow,
            extension=extension,
            prompt=PROMPT,
            extra_pnginfo=EXTRA_PNGINFO,
        )
        path = Path(result["result"][1][0])
        self.addCleanup(tmp.cleanup)
        return path

    def test_png_minimal_embed_false_keeps_parameters_without_workflow(self):
        path = self.save_image("png", "minimal", "false")

        with Image.open(path) as image:
            metadata = image.text

        self.assertEqual({"parameters"}, set(metadata))
        parameters = json.loads(metadata["parameters"])
        self.assertEqual("positive prompt", parameters["positive"])
        self.assertEqual("negative prompt", parameters["negative"])
        self.assertEqual(123, parameters["seed"])
        self.assertEqual("model.safetensors", parameters["model"])

    def test_png_full_embed_false_suppresses_workflow_keys(self):
        path = self.save_image("png", "full", "false")

        with Image.open(path) as image:
            metadata = image.text

        self.assertIn("parameters", metadata)
        self.assertIn("custom", metadata)
        self.assertNotIn("prompt", metadata)
        self.assertNotIn("workflow", metadata)

    def test_png_full_embed_true_keeps_workflow_keys(self):
        path = self.save_image("png", "full", "true")

        with Image.open(path) as image:
            metadata = image.text

        self.assertIn("prompt", metadata)
        self.assertIn("workflow", metadata)

    def test_png_none_writes_no_node_controlled_metadata(self):
        path = self.save_image("png", "none", "false")

        with Image.open(path) as image:
            metadata = image.text

        self.assertEqual({}, metadata)

    def test_webp_minimal_embed_false_keeps_parameters_without_workflow(self):
        path = self.save_image("webp", "minimal", "false")

        with Image.open(path) as image:
            exif = image.getexif()

        self.assertTrue(exif.get(0x010f).startswith("Parameters:"))
        self.assertNotIn("Workflow:", exif.get(0x010e, ""))

    def test_webp_full_embed_false_suppresses_workflow_graph(self):
        path = self.save_image("webp", "full", "false")

        with Image.open(path) as image:
            exif = image.getexif()

        self.assertTrue(exif.get(0x010f).startswith("Parameters:"))
        self.assertNotIn("Workflow:", exif.get(0x010e, ""))


if __name__ == "__main__":
    unittest.main()
