import math
import re

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


MAX_RESIZE_DIMENSION = 16384
MAX_RESIZE_PIXELS = 134_217_728


ASPECT_RATIO_PRESETS = {
    "1:1": (1, 1),
    "3:2": (3, 2),
    "4:3": (4, 3),
    "16:9": (16, 9),
    "2:3": (2, 3),
    "3:4": (3, 4),
    "9:16": (9, 16),
}


def _validate_image(image: torch.Tensor) -> tuple[int, int, int, int]:
    if not isinstance(image, torch.Tensor) or image.dim() != 4:
        raise ValueError("expected IMAGE tensor with shape B,H,W,C")
    batch, height, width, channels = image.shape
    if batch < 1 or height < 1 or width < 1:
        raise ValueError("expected IMAGE tensor with non-empty batch and dimensions")
    if channels not in (1, 3, 4):
        raise ValueError(f"unsupported IMAGE channel count: {channels}")
    return int(batch), int(height), int(width), int(channels)


def _validate_target_dimensions(width: int, height: int) -> tuple[int, int]:
    width = int(width)
    height = int(height)
    if width < 1 or height < 1:
        raise ValueError(f"Invalid target dimensions: {width}x{height}")
    if width > MAX_RESIZE_DIMENSION or height > MAX_RESIZE_DIMENSION:
        raise ValueError(f"Invalid target dimensions: {width}x{height} exceeds supported maximum")
    if width * height > MAX_RESIZE_PIXELS:
        raise ValueError(f"Invalid target dimensions: {width}x{height} exceeds supported pixel budget")
    return width, height


def _round_up_to_multiple(value: int, multiple_value) -> int:
    if str(multiple_value) == "None":
        return int(value)
    multiple = int(multiple_value)
    if multiple <= 1:
        return int(value)
    return int(((int(value) + multiple - 1) // multiple) * multiple)


def _aspect_ratio_value(aspect_ratio: str, proportional_width: int, proportional_height: int, src_w: int, src_h: int) -> float:
    if aspect_ratio == "original":
        return src_w / src_h
    if aspect_ratio == "custom":
        if proportional_width <= 0 or proportional_height <= 0:
            raise ValueError("Invalid custom aspect ratio: proportional dimensions must be positive")
        return proportional_width / proportional_height
    if aspect_ratio in ASPECT_RATIO_PRESETS:
        width, height = ASPECT_RATIO_PRESETS[aspect_ratio]
        return width / height
    if ":" in str(aspect_ratio):
        left, right = str(aspect_ratio).split(":", 1)
        try:
            width = int(left)
            height = int(right)
        except ValueError as exc:
            raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
        return width / height
    raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")


def _parse_background_color(background_color: str, channels: int, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
    text = str(background_color).strip()
    values: list[float]

    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        values = [int(text[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    elif re.fullmatch(r"[0-9.]+\s*,\s*[0-9.]+\s*,\s*[0-9.]+", text):
        raw = [float(part.strip()) for part in text.split(",")]
        if any(value < 0 for value in raw):
            raise ValueError(f"Invalid background_color: {background_color}")
        if any(value > 1.0 for value in raw):
            if any(value > 255.0 for value in raw):
                raise ValueError(f"Invalid background_color: {background_color}")
            values = [value / 255.0 for value in raw]
        else:
            values = raw
    else:
        raise ValueError(f"Invalid background_color: {background_color}")

    if channels == 1:
        gray = 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]
        values = [gray]
    elif channels == 4:
        values = values + [1.0]

    return torch.tensor(values, dtype=dtype, device=device)


def _resize_tensor(image: torch.Tensor, width: int, height: int, method: str) -> torch.Tensor:
    width, height = _validate_target_dimensions(width, height)
    if method == "nvidia_rtx_vsr":
        return _resize_tensor_rtx_vsr(image, width, height)
    if method == "lanczos":
        return _resize_tensor_lanczos(image, width, height)

    mode = {
        "nearest": "nearest",
        "nearest-exact": "nearest-exact",
        "bilinear": "bilinear",
        "bicubic": "bicubic",
        "area": "area",
    }.get(method)
    if mode is None:
        raise ValueError(f"Unknown resize method: {method}")

    nchw = image.permute(0, 3, 1, 2)
    if mode in ("bilinear", "bicubic"):
        resized = F.interpolate(nchw, size=(height, width), mode=mode, align_corners=False)
    else:
        resized = F.interpolate(nchw, size=(height, width), mode=mode)
    return resized.permute(0, 2, 3, 1)


def _resize_mask(mask: torch.Tensor, width: int, height: int) -> torch.Tensor:
    width, height = _validate_target_dimensions(width, height)
    return F.interpolate(mask.unsqueeze(1), size=(height, width), mode="nearest").squeeze(1)


def _resize_tensor_lanczos(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    original_device = image.device
    original_dtype = image.dtype
    outputs = []
    for item in image.detach().to(device="cpu", dtype=torch.float32):
        channels = int(item.shape[-1])
        array = (item.clamp(0.0, 1.0).numpy() * 255.0).round().astype(np.uint8)
        if channels == 1:
            pil = Image.fromarray(array[:, :, 0], mode="L")
        elif channels == 4:
            pil = Image.fromarray(array, mode="RGBA")
        else:
            pil = Image.fromarray(array, mode="RGB")
        resized = pil.resize((width, height), Image.Resampling.LANCZOS)
        out = np.array(resized).astype(np.float32) / 255.0
        if out.ndim == 2:
            out = np.expand_dims(out, axis=-1)
        outputs.append(torch.from_numpy(out))
    return torch.stack(outputs, dim=0).to(device=original_device, dtype=original_dtype)


def _resize_tensor_rtx_vsr(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    if not image.is_cuda:
        raise RuntimeError(
            "NVIDIA RTX Video Super Resolution requires a CUDA image tensor; select device='gpu' "
            "on a CUDA-capable system."
        )

    try:
        import nvvfx  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "NVIDIA RTX Video Super Resolution is not available. Install the NVIDIA VFX Python "
            "package and run on a compatible NVIDIA GPU."
        ) from exc

    original_dtype = image.dtype
    output_width = max(8, width - (width % 8))
    output_height = max(8, height - (height % 8))
    if output_width != width or output_height != height:
        output_width = max(8, int(math.ceil(width / 8) * 8))
        output_height = max(8, int(math.ceil(height / 8) * 8))

    outputs = []
    effect_context = nvvfx.VideoSuperRes(nvvfx.effects.QualityLevel.ULTRA)
    effect = None
    try:
        effect = effect_context.__enter__()
        effect.output_width = output_width
        effect.output_height = output_height
        effect.load()
        for item in image:
            frame = item.permute(2, 0, 1).contiguous()
            outputs.append(torch.from_dlpack(effect.run(frame).image).clone())
    finally:
        effect_context.__exit__(None, None, None)

    resized = torch.stack(outputs, dim=0).permute(0, 2, 3, 1).to(dtype=original_dtype)
    if resized.shape[1] != height or resized.shape[2] != width:
        resized = _resize_tensor(resized, width, height, "bilinear")
    return resized


def _fit_dimensions(src_w: int, src_h: int, target_w: int, target_h: int) -> tuple[int, int]:
    ratio = min(target_w / src_w, target_h / src_h)
    return max(1, round(src_w * ratio)), max(1, round(src_h * ratio))


def _placement(target_w: int, target_h: int, fit_w: int, fit_h: int, crop_position: str) -> tuple[int, int]:
    if crop_position == "top":
        return (target_w - fit_w) // 2, 0
    if crop_position == "bottom":
        return (target_w - fit_w) // 2, target_h - fit_h
    if crop_position == "left":
        return 0, (target_h - fit_h) // 2
    if crop_position == "right":
        return target_w - fit_w, (target_h - fit_h) // 2
    return (target_w - fit_w) // 2, (target_h - fit_h) // 2


def _crop_to_aspect(image: torch.Tensor, mask: torch.Tensor, target_w: int, target_h: int, crop_position: str) -> tuple[torch.Tensor, torch.Tensor]:
    src_h = int(image.shape[1])
    src_w = int(image.shape[2])
    source_aspect = src_w / src_h
    target_aspect = target_w / target_h

    if source_aspect > target_aspect:
        crop_w = max(1, round(src_h * target_aspect))
        crop_h = src_h
    else:
        crop_w = src_w
        crop_h = max(1, round(src_w / target_aspect))

    if crop_position == "left":
        x = 0
        y = (src_h - crop_h) // 2
    elif crop_position == "right":
        x = src_w - crop_w
        y = (src_h - crop_h) // 2
    elif crop_position == "top":
        x = (src_w - crop_w) // 2
        y = 0
    elif crop_position == "bottom":
        x = (src_w - crop_w) // 2
        y = src_h - crop_h
    else:
        x = (src_w - crop_w) // 2
        y = (src_h - crop_h) // 2

    return image[:, y:y + crop_h, x:x + crop_w, :], mask[:, y:y + crop_h, x:x + crop_w]


def _pad_constant(
    resized: torch.Tensor,
    resized_mask: torch.Tensor,
    target_w: int,
    target_h: int,
    background: torch.Tensor,
    crop_position: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    batch, fit_h, fit_w, channels = resized.shape
    output = background.view(1, 1, 1, channels).expand(batch, target_h, target_w, channels).clone()
    out_mask = torch.zeros((batch, target_h, target_w), dtype=resized_mask.dtype, device=resized_mask.device)
    x, y = _placement(target_w, target_h, fit_w, fit_h, crop_position)
    output[:, y:y + fit_h, x:x + fit_w, :] = resized
    out_mask[:, y:y + fit_h, x:x + fit_w] = resized_mask
    return output, out_mask


def _pad_replicate(resized: torch.Tensor, resized_mask: torch.Tensor, target_w: int, target_h: int, crop_position: str) -> tuple[torch.Tensor, torch.Tensor]:
    _batch, fit_h, fit_w, _channels = resized.shape
    x, y = _placement(target_w, target_h, fit_w, fit_h, crop_position)
    left = x
    right = target_w - fit_w - left
    top = y
    bottom = target_h - fit_h - top
    padded = F.pad(resized.permute(0, 3, 1, 2), (left, right, top, bottom), mode="replicate").permute(0, 2, 3, 1)
    out_mask = torch.zeros((resized.shape[0], target_h, target_w), dtype=resized_mask.dtype, device=resized_mask.device)
    out_mask[:, y:y + fit_h, x:x + fit_w] = resized_mask
    return padded, out_mask


def _pad_edge_average(resized: torch.Tensor, resized_mask: torch.Tensor, target_w: int, target_h: int, crop_position: str) -> tuple[torch.Tensor, torch.Tensor]:
    batch, fit_h, fit_w, channels = resized.shape
    output = torch.zeros((batch, target_h, target_w, channels), dtype=resized.dtype, device=resized.device)
    x, y = _placement(target_w, target_h, fit_w, fit_h, crop_position)
    output[:, :, :, :] = resized.mean(dim=(1, 2), keepdim=True)
    if y > 0:
        output[:, :y, :, :] = resized[:, :1, :, :].mean(dim=2, keepdim=True)
    if y + fit_h < target_h:
        output[:, y + fit_h:, :, :] = resized[:, -1:, :, :].mean(dim=2, keepdim=True)
    if x > 0:
        output[:, y:y + fit_h, :x, :] = resized[:, :, :1, :].mean(dim=1, keepdim=True)
    if x + fit_w < target_w:
        output[:, y:y + fit_h, x + fit_w:, :] = resized[:, :, -1:, :].mean(dim=1, keepdim=True)
    output[:, y:y + fit_h, x:x + fit_w, :] = resized
    out_mask = torch.zeros((batch, target_h, target_w), dtype=resized_mask.dtype, device=resized_mask.device)
    out_mask[:, y:y + fit_h, x:x + fit_w] = resized_mask
    return output, out_mask


def _pad_blur_background(
    image: torch.Tensor,
    resized: torch.Tensor,
    resized_mask: torch.Tensor,
    target_w: int,
    target_h: int,
    method: str,
    crop_position: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    src_h = int(image.shape[1])
    src_w = int(image.shape[2])
    fill_ratio = max(target_w / src_w, target_h / src_h)
    fill_w = max(1, round(src_w * fill_ratio))
    fill_h = max(1, round(src_h * fill_ratio))
    background_method = "bilinear" if method in {"lanczos", "nvidia_rtx_vsr"} else method
    background = _resize_tensor(image, fill_w, fill_h, background_method)
    start_x = max(0, (fill_w - target_w) // 2)
    start_y = max(0, (fill_h - target_h) // 2)
    background = background[:, start_y:start_y + target_h, start_x:start_x + target_w, :]
    if background.shape[1] != target_h or background.shape[2] != target_w:
        background = _resize_tensor(background, target_w, target_h, "bilinear")
    nchw = background.permute(0, 3, 1, 2)
    blurred = F.avg_pool2d(nchw, kernel_size=7, stride=1, padding=3).permute(0, 2, 3, 1)
    blurred = torch.clamp(blurred * 0.65, 0.0, 1.0)

    batch, fit_h, fit_w, _channels = resized.shape
    out_mask = torch.zeros((batch, target_h, target_w), dtype=resized_mask.dtype, device=resized_mask.device)
    x, y = _placement(target_w, target_h, fit_w, fit_h, crop_position)
    blurred[:, y:y + fit_h, x:x + fit_w, :] = resized
    out_mask[:, y:y + fit_h, x:x + fit_w] = resized_mask
    return blurred, out_mask


def _prepare_mask(mask: torch.Tensor | None, batch: int, src_w: int, src_h: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor | None:
    if mask is None:
        return None
    if not isinstance(mask, torch.Tensor):
        raise ValueError("expected MASK tensor")
    if mask.dim() == 2:
        mask = mask.unsqueeze(0)
    if mask.dim() != 3:
        raise ValueError("expected MASK tensor with shape B,H,W")
    if mask.shape[0] == 1 and batch > 1:
        mask = mask.repeat(batch, 1, 1)
    if mask.shape[0] != batch:
        raise ValueError("MASK batch size must match IMAGE batch size or be 1")
    mask = mask.to(device=device, dtype=dtype)
    if int(mask.shape[1]) != src_h or int(mask.shape[2]) != src_w:
        mask = _resize_mask(mask, src_w, src_h)
    return mask.clamp(0.0, 1.0)


def _target_from_explicit(width: int, height: int, src_w: int, src_h: int) -> tuple[int, int]:
    width = int(width)
    height = int(height)
    if width < 0 or height < 0:
        raise ValueError("Invalid target dimensions: width and height must be non-negative")
    if width == 0 and height == 0:
        return src_w, src_h
    if width == 0:
        return max(1, round(src_w * (height / src_h))), height
    if height == 0:
        return width, max(1, round(src_h * (width / src_w)))
    return width, height


def _target_from_aspect(
    aspect_ratio: str,
    proportional_width: int,
    proportional_height: int,
    scale_to_side: str,
    scale_to_length: int,
    src_w: int,
    src_h: int,
) -> tuple[int, int]:
    ratio = _aspect_ratio_value(aspect_ratio, int(proportional_width), int(proportional_height), src_w, src_h)
    scale_to_length = int(scale_to_length)
    if scale_to_length < 1:
        raise ValueError("scale_to_length must be positive")

    if ratio > 1:
        if scale_to_side == "longest":
            width = scale_to_length
            height = int(width / ratio)
        elif scale_to_side == "shortest":
            height = scale_to_length
            width = int(height * ratio)
        elif scale_to_side == "width":
            width = scale_to_length
            height = int(width / ratio)
        elif scale_to_side == "height":
            height = scale_to_length
            width = int(height * ratio)
        elif scale_to_side == "total_pixel(kilo pixel)":
            width = int(math.sqrt(ratio * scale_to_length * 1000))
            height = int(width / ratio)
        else:
            width = src_w
            height = int(width / ratio)
    else:
        if scale_to_side == "longest":
            height = scale_to_length
            width = int(height * ratio)
        elif scale_to_side == "shortest":
            width = scale_to_length
            height = int(width / ratio)
        elif scale_to_side == "width":
            width = scale_to_length
            height = int(width / ratio)
        elif scale_to_side == "height":
            height = scale_to_length
            width = int(height * ratio)
        elif scale_to_side == "total_pixel(kilo pixel)":
            width = int(math.sqrt(ratio * scale_to_length * 1000))
            height = int(width / ratio)
        else:
            height = src_h
            width = int(height * ratio)

    return max(1, width), max(1, height)


def _work_device_for_choice(device_choice: str, method: str, current_device: torch.device) -> torch.device:
    if device_choice == "cpu":
        return current_device
    if device_choice != "gpu":
        raise ValueError(f"Unknown device option: {device_choice}")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if method == "nvidia_rtx_vsr":
        raise RuntimeError(
            "NVIDIA RTX Video Super Resolution requires device='gpu' with CUDA available on a "
            "compatible NVIDIA GPU."
        )
    return current_device


class ResizeImageAdvanced:
    @classmethod
    def INPUT_TYPES(cls):
        ratio_list = ["original", "custom", "1:1", "3:2", "4:3", "16:9", "2:3", "3:4", "9:16"]
        fit_modes = [
            "fill",
            "stretch",
            "resize",
            "letterbox",
            "pad",
            "pad_edge",
            "pad_edge_pixel",
            "pillarbox_blur",
            "crop",
            "total_pixels",
        ]
        return {
            "required": {
                "image": ("IMAGE",),
                "resize_mode": (["explicit", "aspect_ratio"],),
                "width": ("INT", {"default": 512, "min": 0, "max": MAX_RESIZE_DIMENSION, "step": 1}),
                "height": ("INT", {"default": 512, "min": 0, "max": MAX_RESIZE_DIMENSION, "step": 1}),
                "aspect_ratio": (ratio_list,),
                "proportional_width": ("INT", {"default": 1, "min": 1, "max": MAX_RESIZE_DIMENSION, "step": 1}),
                "proportional_height": ("INT", {"default": 1, "min": 1, "max": MAX_RESIZE_DIMENSION, "step": 1}),
                "fit": (fit_modes,),
                "method": (["nearest", "nearest-exact", "bilinear", "area", "bicubic", "lanczos", "nvidia_rtx_vsr"],),
                "scale_to_side": (["None", "longest", "shortest", "width", "height", "total_pixel(kilo pixel)"],),
                "scale_to_length": ("INT", {"default": 1024, "min": 1, "max": MAX_RESIZE_DIMENSION, "step": 1}),
                "background_color": ("STRING", {"default": "#000000"}),
                "crop_position": (["center", "top", "bottom", "left", "right"],),
                "round_to_multiple": ("INT", {"default": 0, "min": 0, "max": 512, "step": 1}),
                "device": (["cpu", "gpu"],),
            },
            "optional": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "MASK")
    RETURN_NAMES = ("image", "width", "height", "mask")
    FUNCTION = "resize"
    CATEGORY = "ComfyUI Text Processor/Image"
    DESCRIPTION = "Resizes image batches with KJ-style resize modes plus aspect-ratio target calculation and mask alignment."
    SEARCH_ALIASES = ["resize image", "image scale", "aspect ratio resize", "letterbox", "image pad"]
    OUTPUT_TOOLTIPS = (
        "Resized image batch.",
        "Final output width.",
        "Final output height.",
        "Mask aligned to the resized image, or an empty mask when no mask is supplied.",
    )

    def resize(
        self,
        image,
        resize_mode,
        width,
        height,
        aspect_ratio,
        proportional_width,
        proportional_height,
        fit,
        method,
        scale_to_side,
        scale_to_length,
        background_color,
        crop_position,
        round_to_multiple,
        device,
        mask=None,
    ):
        batch, src_h, src_w, channels = _validate_image(image)
        original_device = image.device
        image = image.clamp(0.0, 1.0)
        work_device = _work_device_for_choice(str(device), str(method), original_device)
        if work_device != image.device:
            image = image.to(device=work_device)
        source_mask = _prepare_mask(mask, batch, src_w, src_h, image.device, image.dtype)
        if source_mask is None:
            source_mask = torch.ones((batch, src_h, src_w), dtype=image.dtype, device=image.device)
            mask_was_supplied = False
        else:
            mask_was_supplied = True

        if fit == "total_pixels":
            total_pixels = int(width) * int(height)
            if total_pixels < 1:
                raise ValueError("Invalid target dimensions: total_pixels requires positive width and height")
            ratio = src_w / src_h
            target_w = int(math.sqrt(total_pixels * ratio))
            target_h = int(math.sqrt(total_pixels / ratio))
        elif resize_mode == "aspect_ratio":
            target_w, target_h = _target_from_aspect(
                aspect_ratio,
                int(proportional_width),
                int(proportional_height),
                scale_to_side,
                int(scale_to_length),
                src_w,
                src_h,
            )
        else:
            target_w, target_h = _target_from_explicit(int(width), int(height), src_w, src_h)

        target_w = _round_up_to_multiple(target_w, round_to_multiple)
        target_h = _round_up_to_multiple(target_h, round_to_multiple)
        target_w, target_h = _validate_target_dimensions(target_w, target_h)

        fit = "fill" if fit == "stretch" else fit
        fit = "letterbox" if fit == "pad" else fit

        if fit == "total_pixels":
            fit = "resize"

        if fit == "resize":
            out_w, out_h = _fit_dimensions(src_w, src_h, target_w, target_h)
            out_w, out_h = _validate_target_dimensions(out_w, out_h)
            out_image = _resize_tensor(image, out_w, out_h, method)
            out_mask = _resize_mask(source_mask, out_w, out_h)
        elif fit == "fill":
            out_w, out_h = target_w, target_h
            out_image = _resize_tensor(image, out_w, out_h, method)
            out_mask = _resize_mask(source_mask, out_w, out_h)
        elif fit == "crop":
            cropped_image, cropped_mask = _crop_to_aspect(image, source_mask, target_w, target_h, crop_position)
            out_w, out_h = target_w, target_h
            out_image = _resize_tensor(cropped_image, out_w, out_h, method)
            out_mask = _resize_mask(cropped_mask, out_w, out_h)
        elif fit in {"letterbox", "pad_edge", "pad_edge_pixel", "pillarbox_blur"}:
            fit_w, fit_h = _fit_dimensions(src_w, src_h, target_w, target_h)
            resized = _resize_tensor(image, fit_w, fit_h, method)
            resized_mask = _resize_mask(source_mask, fit_w, fit_h)
            out_w, out_h = target_w, target_h
            if fit == "letterbox":
                background = _parse_background_color(background_color, channels, image.dtype, image.device)
                out_image, out_mask = _pad_constant(resized, resized_mask, target_w, target_h, background, crop_position)
            elif fit == "pad_edge":
                out_image, out_mask = _pad_edge_average(resized, resized_mask, target_w, target_h, crop_position)
            elif fit == "pad_edge_pixel":
                out_image, out_mask = _pad_replicate(resized, resized_mask, target_w, target_h, crop_position)
            else:
                out_image, out_mask = _pad_blur_background(image, resized, resized_mask, target_w, target_h, method, crop_position)
        else:
            raise ValueError(f"Unknown fit mode: {fit}")

        if not mask_was_supplied:
            out_mask = torch.zeros((batch, out_h, out_w), dtype=image.dtype, device=image.device)

        if out_image.device != original_device:
            out_image = out_image.to(device=original_device)
        if out_mask.device != original_device:
            out_mask = out_mask.to(device=original_device)

        return (out_image, int(out_w), int(out_h), out_mask)


NODE_CLASS_MAPPINGS = {
    "ResizeImageAdvanced": ResizeImageAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ResizeImageAdvanced": "Resize Image Advanced",
}
