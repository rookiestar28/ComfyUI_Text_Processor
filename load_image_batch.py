import glob
import os
import random
from pathlib import Path, PureWindowsPath

import numpy as np
import torch
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_IMAGE_EXTENSIONS = (".jpeg", ".jpg", ".png", ".tiff", ".gif", ".bmp", ".webp")


def pil_to_tensor(image: Image.Image) -> torch.Tensor:
    array = np.array(image).astype(np.float32) / 255.0
    if array.ndim == 2:
        array = np.expand_dims(array, axis=-1)
    return torch.from_numpy(array).unsqueeze(0)


class LoadImageBatch:
    _incremental_state: dict[str, dict[str, object]] = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["single_image", "incremental_image", "random"],),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "index": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "label": ("STRING", {"default": "Batch 001", "multiline": False}),
                "path": ("STRING", {"default": "", "multiline": False}),
                "pattern": ("STRING", {"default": "*", "multiline": False}),
                "allow_RGBA_output": (["false", "true"],),
            },
            "optional": {
                "filename_text_extension": (["true", "false"],),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "filename_text")
    FUNCTION = "load_batch_images"
    CATEGORY = "ComfyUI Text Processor/Image"
    DESCRIPTION = "Loads one image from a directory batch using single, incremental, or seeded-random selection."
    SEARCH_ALIASES = ["load image batch", "batch image loader", "image directory", "load folder images"]

    @classmethod
    def clear_state(cls):
        cls._incremental_state.clear()

    @staticmethod
    def _validate_pattern(pattern: str) -> str:
        pattern = pattern or "*"
        normalized = pattern.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        windows_path = PureWindowsPath(pattern)
        # CRITICAL: pattern is workflow-controlled; keep glob expansion inside the selected directory.
        if normalized.startswith("/") or normalized.startswith("//") or windows_path.drive or ".." in parts:
            raise ValueError(f"Unsafe image pattern: {pattern!r}")
        return pattern

    @staticmethod
    def _list_image_paths(directory_path: str, pattern: str) -> list[Path]:
        if not directory_path or not os.path.isdir(directory_path):
            raise ValueError(f"Load Image Batch path does not exist or is not a directory: {directory_path!r}")

        pattern = LoadImageBatch._validate_pattern(pattern)
        glob_pattern = os.path.join(glob.escape(directory_path), pattern)
        paths = []
        for file_name in glob.glob(glob_pattern, recursive=True):
            path = Path(file_name)
            if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                paths.append(path.resolve())

        paths.sort(key=lambda path: str(path).casefold())
        if not paths:
            raise ValueError(
                f"No images found in {directory_path!r} matching pattern {pattern!r}. "
                f"Allowed extensions: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )
        return paths

    @classmethod
    def _next_incremental_index(cls, label: str, directory_path: str, pattern: str, count: int) -> int:
        key = str(label)
        signature = (str(Path(directory_path).resolve()), pattern)
        state = cls._incremental_state.get(key)
        if state is None or state.get("signature") != signature:
            index = 0
        else:
            index = int(state.get("next_index", 0))

        if index >= count:
            index = 0

        cls._incremental_state[key] = {
            "signature": signature,
            "next_index": (index + 1) % count,
        }
        return index

    @staticmethod
    def _choose_index(mode: str, index: int, seed: int, image_paths: list[Path], label: str, path: str, pattern: str) -> int:
        if mode == "single_image":
            if index < 0 or index >= len(image_paths):
                raise ValueError(f"Invalid image index {index}; valid range is 0..{len(image_paths) - 1}.")
            return index

        if mode == "incremental_image":
            return LoadImageBatch._next_incremental_index(label, path, pattern, len(image_paths))

        if mode == "random":
            rng = random.Random(seed)
            return rng.randrange(len(image_paths))

        raise ValueError(f"Unknown Load Image Batch mode: {mode}")

    @staticmethod
    def _load_image(path: Path, allow_rgba_output: bool) -> Image.Image:
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                if allow_rgba_output:
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                else:
                    image = image.convert("RGB")
                return image.copy()
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError(f"Failed to load image {str(path)!r}: {exc}") from exc

    def load_batch_images(
        self,
        path,
        pattern="*",
        index=0,
        mode="single_image",
        seed=0,
        label="Batch 001",
        allow_RGBA_output="false",
        filename_text_extension="true",
    ):
        image_paths = self._list_image_paths(str(path), str(pattern))
        chosen_index = self._choose_index(
            mode=str(mode),
            index=int(index),
            seed=int(seed),
            image_paths=image_paths,
            label=str(label),
            path=str(path),
            pattern=str(pattern),
        )
        chosen_path = image_paths[chosen_index]
        image = self._load_image(chosen_path, allow_rgba_output=(allow_RGBA_output == "true"))
        filename = chosen_path.name if filename_text_extension == "true" else chosen_path.stem
        return (pil_to_tensor(image), filename)


NODE_CLASS_MAPPINGS = {
    # IMPORTANT: keep the node id distinct from WAS Suite's "Load Image Batch" id to avoid ComfyUI registration collisions.
    "LoadImageBatch": LoadImageBatch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageBatch": "Load Image Batch",
}
