"""V1 ComfyUI adapter for the deterministic resolution-planning core."""

from __future__ import annotations

import math
import random
from typing import Callable

try:
    from .advanced_resolution_selector_core import (
        DIRECTIONS,
        LEGACY_PRESET_LABELS,
        PUBLIC_PRESETS,
        AspectRatio,
        ResolutionRequest,
        canonical_ratio,
        normalize_ratio,
        plan_resolution,
    )
except ImportError:
    # IMPORTANT: retain direct-module discovery for the repository's unittest lane.
    from advanced_resolution_selector_core import (
        DIRECTIONS,
        LEGACY_PRESET_LABELS,
        PUBLIC_PRESETS,
        AspectRatio,
        ResolutionRequest,
        canonical_ratio,
        normalize_ratio,
        plan_resolution,
    )


NODE_ID = "TP_AdvancedResolutionSelector"
DISPLAY_NAME = "Advanced Resolution Selector"
OUTPUT_MODES = ("fixed", "randomize", "randomize_all")
RATIO_LABELS = tuple(ratio.label for ratio in PUBLIC_PRESETS)
ASPECT_RATIO_OPTIONS = RATIO_LABELS + ("custom",)
EXECUTABLE_RATIO_LABELS = RATIO_LABELS + LEGACY_PRESET_LABELS + ("custom",)
DrawStream = Callable[[], object]


def _invalid(identifier: str) -> None:
    messages = {
        "output_mode": "invalid_output_mode: a supported output mode is required",
        "aspect_ratio": "invalid_aspect_ratio: a supported ratio preset or custom is required",
        "seed": "invalid_seed: an integer seed in 0..4294967295 is required",
        "draw": "invalid_draw: a finite value in the half-open interval [0, 1) is required",
        "draw_stream": "invalid_draw_stream: a callable draw stream is required",
    }
    raise ValueError(messages[identifier])


def _validate_seed(seed: object) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 4294967295:
        _invalid("seed")


def _validate_draw(draw: object) -> float:
    if isinstance(draw, bool) or not isinstance(draw, (int, float)):
        _invalid("draw")
    try:
        finite = math.isfinite(float(draw))
    except (OverflowError, ValueError):
        finite = False
    if not finite or not 0.0 <= draw < 1.0:
        _invalid("draw")
    return float(draw)


def _resolve_selection(
    output_mode: object,
    aspect_ratio: object,
    direction: object,
    custom_ratio_width: object,
    custom_ratio_height: object,
    megapixels: object,
    multiple: object,
    seed: object,
    *,
    draw_stream: DrawStream | None = None,
) -> tuple[AspectRatio, str]:
    """Resolve ratio and direction while preserving the frozen draw contract."""

    if not isinstance(output_mode, str) or output_mode not in OUTPUT_MODES:
        _invalid("output_mode")
    # IMPORTANT: legacy 21:9 stays executable without returning to the public menu or RNG pool.
    if not isinstance(aspect_ratio, str) or aspect_ratio not in EXECUTABLE_RATIO_LABELS:
        _invalid("aspect_ratio")

    # Validate custom components for every mode before selecting a candidate or RNG.
    custom = normalize_ratio(custom_ratio_width, custom_ratio_height)
    selected_ratio = custom if aspect_ratio == "custom" else canonical_ratio(aspect_ratio)

    # ResolutionRequest performs the accepted F21 direction/megapixel/multiple checks.
    ResolutionRequest(selected_ratio, direction, megapixels, multiple)
    _validate_seed(seed)

    if output_mode == "fixed":
        return selected_ratio, direction

    if draw_stream is None:
        draw_stream = random.Random(seed).random
    elif not callable(draw_stream):
        _invalid("draw_stream")

    def next_index(pool_size: int) -> int:
        return int(_validate_draw(draw_stream()) * pool_size)

    if output_mode == "randomize":
        return selected_ratio, DIRECTIONS[next_index(len(DIRECTIONS))]

    sampled_ratio = PUBLIC_PRESETS[next_index(len(PUBLIC_PRESETS))]
    sampled_direction = DIRECTIONS[next_index(len(DIRECTIONS))]
    return sampled_ratio, sampled_direction


class AdvancedResolutionSelector:
    DESCRIPTION = (
        "Selects a deterministic, multiple-aligned image resolution from canonical "
        "or custom aspect ratios."
    )
    SEARCH_ALIASES = (
        "advanced resolution selector",
        "resolution selector",
        "aspect ratio",
        "seeded resolution",
    )
    RETURN_TYPES = ("INT", "INT", "STRING", "STRING", "FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = (
        "width",
        "height",
        "resolved_aspect_ratio",
        "resolved_direction",
        "actual_megapixels",
        "pixel_error_percent",
        "aspect_error_percent",
    )
    OUTPUT_TOOLTIPS = (
        "Aligned output width in pixels.",
        "Aligned output height in pixels.",
        "Canonical or reduced custom ratio label before direction is reported separately.",
        "Resolved landscape or portrait direction.",
        "Realized binary megapixels after multiple alignment.",
        "Signed realized pixel-area error percentage.",
        "Signed realized aspect-ratio error percentage.",
    )
    FUNCTION = "select_resolution"
    CATEGORY = "ComfyUI Text Processor/Image"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "output_mode": (
                    list(OUTPUT_MODES),
                    {
                        "default": "fixed",
                        "tooltip": "Select fixed, seeded direction randomization, or seeded preset and direction randomization.",
                    },
                ),
                "aspect_ratio": (
                    list(ASPECT_RATIO_OPTIONS),
                    {
                        "default": "1:1",
                        "tooltip": "Choose one canonical ratio or provide a positive custom ratio pair.",
                    },
                ),
                "direction": (
                    list(DIRECTIONS),
                    {
                        "default": "landscape",
                        "tooltip": "Choose the resolved orientation; randomized modes may replace it with a seeded draw.",
                    },
                ),
                "custom_ratio_width": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 10000,
                        "step": 1,
                        "advanced": True,
                        "tooltip": "Positive custom ratio width; used when aspect_ratio is custom.",
                    },
                ),
                "custom_ratio_height": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 10000,
                        "step": 1,
                        "advanced": True,
                        "tooltip": "Positive custom ratio height; used when aspect_ratio is custom.",
                    },
                ),
                "megapixels": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.1,
                        "max": 16.0,
                        "step": 0.1,
                        "tooltip": "Binary 1024 squared pixel budget before multiple alignment.",
                    },
                ),
                "multiple": (
                    "INT",
                    {
                        "default": 8,
                        "min": 8,
                        "max": 128,
                        "step": 4,
                        "advanced": True,
                        "tooltip": "Align both dimensions to this positive multiple.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 4294967295,
                        "step": 1,
                        "control_after_generate": True,
                        "tooltip": "Explicit uint32 seed for deterministic randomized modes.",
                    },
                ),
            }
        }

    def select_resolution(
        self,
        output_mode,
        aspect_ratio,
        direction,
        custom_ratio_width,
        custom_ratio_height,
        megapixels,
        multiple,
        seed,
    ):
        resolved_ratio, resolved_direction = _resolve_selection(
            output_mode,
            aspect_ratio,
            direction,
            custom_ratio_width,
            custom_ratio_height,
            megapixels,
            multiple,
            seed,
        )
        result = plan_resolution(
            ResolutionRequest(resolved_ratio, resolved_direction, megapixels, multiple)
        )
        result_values = (
            result.width,
            result.height,
            result.resolved_aspect_ratio,
            result.resolved_direction,
            result.actual_megapixels,
            result.pixel_error_percent,
            result.aspect_error_percent,
        )
        return {
            "ui": {
                "tp_advanced_resolution": [
                    {"width": result.width, "height": result.height}
                ]
            },
            "result": result_values,
        }


NODE_CLASS_MAPPINGS = {NODE_ID: AdvancedResolutionSelector}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: DISPLAY_NAME}
