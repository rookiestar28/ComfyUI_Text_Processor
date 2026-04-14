import torch
import torch.nn.functional as F


def _unwrap_scalar_list(value: object, name: str):
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            raise ValueError(f"Empty list provided for '{name}'.")
        first = value[0]
        if any(v != first for v in value[1:]):
            raise ValueError(f"List values for '{name}' must all be identical.")
        return first
    return value


def _to_channels(image: torch.Tensor, channels: int) -> torch.Tensor:
    current = image.shape[-1]
    if current == channels:
        return image

    if current > channels:
        return image[..., :channels]

    if current == 1 and channels in (3, 4):
        rgb = image.repeat(1, 1, 1, 3)
        if channels == 3:
            return rgb
        alpha = torch.ones((*rgb.shape[:-1], 1), device=rgb.device, dtype=rgb.dtype)
        return torch.cat([rgb, alpha], dim=-1)

    pad = torch.ones((*image.shape[:-1], channels - current), device=image.device, dtype=image.dtype)
    return torch.cat([image, pad], dim=-1)


def _resize_bhwc(image: torch.Tensor, new_h: int, new_w: int, interpolation: str) -> torch.Tensor:
    if new_h < 1 or new_w < 1:
        raise ValueError(f"Invalid resize target: {new_w}x{new_h}.")

    mode = {
        "nearest": "nearest",
        "bilinear": "bilinear",
        "bicubic": "bicubic",
    }.get(interpolation, "bicubic")

    nchw = image.permute(0, 3, 1, 2)
    if mode in ("bilinear", "bicubic"):
        try:
            resized = F.interpolate(
                nchw,
                size=(new_h, new_w),
                mode=mode,
                align_corners=False,
                antialias=True,
            )
        except TypeError:
            resized = F.interpolate(
                nchw,
                size=(new_h, new_w),
                mode=mode,
                align_corners=False,
            )
    else:
        resized = F.interpolate(nchw, size=(new_h, new_w), mode=mode)
    return resized.permute(0, 2, 3, 1)


def _normalize_direction(direction: str) -> str:
    aliases = {
        "right": "left_to_right",
        "left": "right_to_left",
        "down": "top_to_bottom",
        "up": "bottom_to_top",
    }
    direction = aliases.get(direction, direction)
    if direction not in {
        "left_to_right",
        "right_to_left",
        "top_to_bottom",
        "bottom_to_top",
    }:
        raise ValueError(f"Unknown direction: {direction}")
    return direction


def _split_to_single_images(images: object) -> list[torch.Tensor]:
    if isinstance(images, torch.Tensor):
        if images.dim() == 3:
            return [images.unsqueeze(0)]
        if images.dim() != 4:
            raise ValueError(f"Expected IMAGE tensor with 3 or 4 dims, got {images.dim()}.")
        return [images[i : i + 1] for i in range(images.shape[0])]

    if isinstance(images, (list, tuple)):
        out: list[torch.Tensor] = []
        for item in images:
            out.extend(_split_to_single_images(item))
        return out

    raise ValueError(f"Unsupported images input type: {type(images)}")


def _fit_to_cell(
    image: torch.Tensor,
    cell_h: int,
    cell_w: int,
    interpolation: str,
    output_channels: int,
) -> torch.Tensor:
    image = _to_channels(image, output_channels)
    if image.dim() != 4 or image.shape[0] != 1:
        raise ValueError("Expected a single image tensor with batch=1.")

    src_h, src_w = image.shape[1], image.shape[2]
    if src_h <= 0 or src_w <= 0:
        raise ValueError("IMAGE has invalid dimensions.")

    scale = min(cell_w / src_w, cell_h / src_h)
    new_h = max(1, min(cell_h, int(round(src_h * scale))))
    new_w = max(1, min(cell_w, int(round(src_w * scale))))
    resized = _resize_bhwc(image, new_h, new_w, interpolation)

    cell = torch.zeros(
        (1, cell_h, cell_w, output_channels),
        device=image.device,
        dtype=image.dtype,
    )
    y = (cell_h - new_h) // 2
    x = (cell_w - new_w) // 2
    cell[:, y : y + new_h, x : x + new_w, :] = resized
    return cell


def _grid_shape(image_count: int, max_images_per_line: int, direction: str) -> tuple[int, int]:
    if image_count < 1:
        raise ValueError("No images provided.")
    if max_images_per_line < 1:
        raise ValueError("max_images_per_line must be at least 1.")

    line = min(max_images_per_line, image_count)
    other = (image_count + line - 1) // line
    if direction in ("left_to_right", "right_to_left"):
        return other, line
    return line, other


def _grid_position(index: int, rows: int, cols: int, direction: str) -> tuple[int, int]:
    if direction == "left_to_right":
        return index // cols, index % cols
    if direction == "right_to_left":
        return index // cols, cols - 1 - (index % cols)
    if direction == "top_to_bottom":
        return index % rows, index // rows
    if direction == "bottom_to_top":
        return rows - 1 - (index % rows), index // rows
    raise ValueError(f"Unknown direction: {direction}")


class TP_ImageConcatenateMulti:
    INPUT_IS_LIST = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "direction": (
                    [
                        "left_to_right",
                        "right_to_left",
                        "top_to_bottom",
                        "bottom_to_top",
                        "right",
                        "left",
                        "down",
                        "up",
                    ],
                    {"default": "left_to_right"},
                ),
                "max_images_per_line": ("INT", {"default": 3, "min": 1, "max": 255, "step": 1}),
                "interpolation": (["bicubic", "bilinear", "nearest"], {"default": "bicubic"}),
                "output_channels": (["rgb", "rgba", "auto"], {"default": "rgb"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "concatenate"
    CATEGORY = "ComfyUI Text Processor/Image"

    def concatenate(
        self,
        images,
        direction,
        max_images_per_line,
        interpolation,
        output_channels,
    ):
        direction = _unwrap_scalar_list(direction, "direction")
        max_images_per_line = int(_unwrap_scalar_list(max_images_per_line, "max_images_per_line"))
        interpolation = _unwrap_scalar_list(interpolation, "interpolation")
        output_channels = _unwrap_scalar_list(output_channels, "output_channels")
        direction = _normalize_direction(direction)

        chosen = _split_to_single_images(images)
        if not chosen:
            raise ValueError("No images provided.")

        if output_channels == "auto":
            max_c = 0
            for img in chosen:
                max_c = max(max_c, int(img.shape[-1]))
            out_c = 4 if max_c >= 4 else 3
        elif output_channels == "rgba":
            out_c = 4
        else:
            out_c = 3

        first = chosen[0]
        if first.dim() != 4 or first.shape[0] != 1:
            raise ValueError("Internal error: expected a single image tensor with batch=1.")

        cell_h, cell_w = int(first.shape[1]), int(first.shape[2])
        rows, cols = _grid_shape(len(chosen), max_images_per_line, direction)
        blank = torch.zeros((1, cell_h, cell_w, out_c), device=first.device, dtype=first.dtype)
        cells = [[blank.clone() for _ in range(cols)] for _ in range(rows)]

        for idx, image in enumerate(chosen):
            row, col = _grid_position(idx, rows, cols, direction)
            cells[row][col] = _fit_to_cell(
                image,
                cell_h=cell_h,
                cell_w=cell_w,
                interpolation=interpolation,
                output_channels=out_c,
            )

        row_tensors = [torch.cat(row_cells, dim=2) for row_cells in cells]
        return (torch.cat(row_tensors, dim=1),)


NODE_CLASS_MAPPINGS = {
    "image_concat_advanced": TP_ImageConcatenateMulti,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "image_concat_advanced": "Image Concat Advanced",
}
