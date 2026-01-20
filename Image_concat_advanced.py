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


def _concat_two(
    image1: torch.Tensor,
    image2: torch.Tensor,
    direction: str,
    first_image_shape: tuple[int, int, int, int],
    output_channels: int,
    interpolation: str,
) -> torch.Tensor:
    image1 = _to_channels(image1, output_channels)
    image2 = _to_channels(image2, output_channels)

    target_h, target_w = first_image_shape[1], first_image_shape[2]
    src_h, src_w = image2.shape[1], image2.shape[2]
    if src_h <= 0 or src_w <= 0:
        raise ValueError("IMAGE has invalid dimensions.")
    aspect = src_w / src_h

    if direction in ("left", "right"):
        new_h = target_h
        new_w = max(1, int(round(new_h * aspect)))
    else:
        new_w = target_w
        new_h = max(1, int(round(new_w / aspect)))
    image2 = _resize_bhwc(image2, new_h, new_w, interpolation)

    if direction == "right":
        return torch.cat((image1, image2), dim=2)
    if direction == "down":
        return torch.cat((image1, image2), dim=1)
    if direction == "left":
        return torch.cat((image2, image1), dim=2)
    if direction == "up":
        return torch.cat((image2, image1), dim=1)
    raise ValueError(f"Unknown direction: {direction}")


class TP_ImageConcatenateMulti:
    INPUT_IS_LIST = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "direction": (["right", "down", "left", "up"], {"default": "right"}),
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
        interpolation,
        output_channels,
    ):
        direction = _unwrap_scalar_list(direction, "direction")
        interpolation = _unwrap_scalar_list(interpolation, "interpolation")
        output_channels = _unwrap_scalar_list(output_channels, "output_channels")

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

        first_shape = first.shape
        current = _to_channels(first, out_c)

        for nxt in chosen[1:]:
            current = _concat_two(
                current,
                nxt,
                direction=direction,
                first_image_shape=first_shape,
                output_channels=out_c,
                interpolation=interpolation,
            )

        return (current,)


NODE_CLASS_MAPPINGS = {
    "image_concat_advanced": TP_ImageConcatenateMulti,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "image_concat_advanced": "Image Concat Advanced",
}
