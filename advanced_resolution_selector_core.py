"""Pure, host-independent resolution planning primitives."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Final


MIN_RATIO_COMPONENT: Final = 1
MAX_RATIO_COMPONENT: Final = 10000
MIN_MEGAPIXELS: Final = 0.1
MAX_MEGAPIXELS: Final = 16.0
MIN_MULTIPLE: Final = 8
MAX_MULTIPLE: Final = 128
MULTIPLE_STEP: Final = 4
MAX_DIMENSION: Final = 409752
PIXEL_UNIT: Final = 1024 * 1024
DIRECTIONS: Final = ("landscape", "portrait")
SCORE_ORDER: Final = (
    "max_abs_error",
    "sum_abs_error",
    "abs_pixel_error",
    "abs_aspect_error",
    "native_manhattan_distance",
    "width",
    "height",
)
_CANONICAL_LABEL_PAIRS: Final = (
    ("1:1", (1, 1)),
    ("9:7", (9, 7)),
    ("4:3", (4, 3)),
    ("19:13", (19, 13)),
    ("3:2", (3, 2)),
    ("7:4", (7, 4)),
    ("16:9", (16, 9)),
    ("21:9", (21, 9)),
)
_ERROR_MESSAGES: Final = (
    ("invalid_ratio", "invalid_ratio: positive integer ratio components in 1..10000 are required"),
    ("invalid_direction", "invalid_direction: direction must be landscape or portrait"),
    ("invalid_megapixels", "invalid_megapixels: finite value in 0.1..16.0 is required"),
    ("invalid_multiple", "invalid_multiple: integer value in 8..128 is required"),
    ("invalid_multiple_step", "invalid_multiple_step: multiple must equal 8 + 4*n"),
    ("invalid_numeric", "invalid_numeric: derived resolution value is not finite"),
    ("invalid_dimension_bound", "invalid_dimension_bound: aligned dimension exceeds 409752 pixels"),
)


def _raise_error(identifier: str) -> None:
    for known_identifier, message in _ERROR_MESSAGES:
        if identifier == known_identifier:
            raise ValueError(message)
    raise ValueError("invalid_numeric: derived resolution value is not finite")


def _valid_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_ratio_components(width: object, height: object) -> None:
    if not _valid_integer(width) or not _valid_integer(height):
        _raise_error("invalid_ratio")
    if not MIN_RATIO_COMPONENT <= width <= MAX_RATIO_COMPONENT:
        _raise_error("invalid_ratio")
    if not MIN_RATIO_COMPONENT <= height <= MAX_RATIO_COMPONENT:
        _raise_error("invalid_ratio")


def _safe_label(label: object) -> bool:
    if not isinstance(label, str) or label.count(":") != 1:
        return False
    left, right = label.split(":")
    return left.isdigit() and right.isdigit() and int(left) > 0 and int(right) > 0


@dataclass(frozen=True, slots=True)
class AspectRatio:
    width: int
    height: int
    label: str

    def __post_init__(self) -> None:
        if not _valid_integer(self.width) or not _valid_integer(self.height):
            _raise_error("invalid_ratio")
        if (
            not MIN_RATIO_COMPONENT <= self.width <= MAX_RATIO_COMPONENT
            or not MIN_RATIO_COMPONENT <= self.height <= MAX_RATIO_COMPONENT
            or math.gcd(self.width, self.height) != 1
        ):
            _raise_error("invalid_ratio")
        if not _safe_label(self.label):
            _raise_error("invalid_ratio")
        label_width, label_height = (int(part) for part in self.label.split(":"))
        canonical_alias = False
        for known_label, (known_width, known_height) in _CANONICAL_LABEL_PAIRS:
            if self.label == known_label:
                divisor = math.gcd(known_width, known_height)
                canonical_alias = (known_width // divisor, known_height // divisor) == (
                    self.width,
                    self.height,
                )
                break
        if (label_width, label_height) != (self.width, self.height) and not canonical_alias:
            _raise_error("invalid_ratio")


def normalize_ratio(width: object, height: object, label: object = None) -> AspectRatio:
    """Validate and reduce a positive ratio pair into an immutable value."""

    _validate_ratio_components(width, height)
    divisor = math.gcd(width, height)
    reduced_width = width // divisor
    reduced_height = height // divisor
    reduced_label = f"{reduced_width}:{reduced_height}"
    if label is None:
        resolved_label = reduced_label
    else:
        if not _safe_label(label):
            _raise_error("invalid_ratio")
        canonical_pair = None
        for known_label, pair in _CANONICAL_LABEL_PAIRS:
            if label == known_label:
                canonical_pair = pair
                break
        if canonical_pair is not None:
            if (width, height) != canonical_pair:
                _raise_error("invalid_ratio")
            resolved_label = label
        elif label != reduced_label:
            _raise_error("invalid_ratio")
        else:
            resolved_label = label
    return AspectRatio(reduced_width, reduced_height, resolved_label)


def canonical_ratio(label: object) -> AspectRatio:
    for known_label, pair in _CANONICAL_LABEL_PAIRS:
        if label == known_label:
            return normalize_ratio(pair[0], pair[1], label=known_label)
    _raise_error("invalid_ratio")
    raise AssertionError("unreachable")


CANONICAL_PRESETS: Final = tuple(canonical_ratio(label) for label, _pair in _CANONICAL_LABEL_PAIRS)


def _validate_direction(direction: object) -> None:
    if not isinstance(direction, str) or direction not in DIRECTIONS:
        _raise_error("invalid_direction")


def _validate_megapixels(megapixels: object) -> None:
    if isinstance(megapixels, bool) or not isinstance(megapixels, (int, float)):
        _raise_error("invalid_megapixels")
    try:
        finite_value = math.isfinite(float(megapixels))
    except (OverflowError, ValueError):
        finite_value = False
    if not finite_value or not MIN_MEGAPIXELS <= megapixels <= MAX_MEGAPIXELS:
        _raise_error("invalid_megapixels")


def _validate_multiple(multiple: object) -> None:
    if not _valid_integer(multiple) or not MIN_MULTIPLE <= multiple <= MAX_MULTIPLE:
        _raise_error("invalid_multiple")
    if (multiple - MIN_MULTIPLE) % MULTIPLE_STEP:
        _raise_error("invalid_multiple_step")


@dataclass(frozen=True, slots=True)
class ResolutionRequest:
    aspect_ratio: AspectRatio
    direction: str
    megapixels: float
    multiple: int

    def __post_init__(self) -> None:
        if not isinstance(self.aspect_ratio, AspectRatio):
            _raise_error("invalid_ratio")
        _validate_direction(self.direction)
        _validate_megapixels(self.megapixels)
        _validate_multiple(self.multiple)


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    width: int
    height: int
    resolved_aspect_ratio: str
    resolved_direction: str
    actual_megapixels: float
    pixel_error_percent: float
    realized_aspect_ratio: float
    aspect_error_percent: float


def _axis_candidates(ideal: float, multiple: int) -> tuple[int, ...]:
    index = ideal / multiple
    if not math.isfinite(index):
        _raise_error("invalid_numeric")
    rounded = round(index)
    candidates = sorted(
        {
            candidate
            for candidate in (
                rounded,
                math.floor(index),
                math.ceil(index),
                rounded - 1,
                rounded + 1,
            )
            if candidate >= 1
        }
    )
    if not candidates or candidates[-1] * multiple > MAX_DIMENSION:
        _raise_error("invalid_dimension_bound")
    return tuple(candidates)


def _candidate_score(
    width_index: int,
    height_index: int,
    multiple: int,
    target_pixels: float,
    oriented_ratio: float,
    native_width_index: int,
    native_height_index: int,
) -> tuple[float, float, float, float, int, int, int]:
    width = width_index * multiple
    height = height_index * multiple
    actual_pixels = width * height
    pixel_error = (actual_pixels / target_pixels - 1) * 100
    aspect_error = ((width / height) / oriented_ratio - 1) * 100
    return (
        max(abs(pixel_error), abs(aspect_error)),
        abs(pixel_error) + abs(aspect_error),
        abs(pixel_error),
        abs(aspect_error),
        abs(width_index - native_width_index) + abs(height_index - native_height_index),
        width,
        height,
    )


def plan_resolution(request: ResolutionRequest) -> ResolutionResult:
    """Plan one deterministic aligned resolution for a validated request."""

    if not isinstance(request, ResolutionRequest):
        _raise_error("invalid_numeric")
    ratio = request.aspect_ratio
    oriented_ratio = ratio.width / ratio.height
    if request.direction == "portrait":
        oriented_ratio = 1 / oriented_ratio
    target_pixels = request.megapixels * PIXEL_UNIT
    ideal_width = math.sqrt(target_pixels * oriented_ratio)
    ideal_height = math.sqrt(target_pixels / oriented_ratio)
    if not all(math.isfinite(value) for value in (oriented_ratio, target_pixels, ideal_width, ideal_height)):
        _raise_error("invalid_numeric")

    width_candidates = _axis_candidates(ideal_width, request.multiple)
    height_candidates = _axis_candidates(ideal_height, request.multiple)
    native_width_index = max(1, round(ideal_width / request.multiple))
    native_height_index = max(1, round(ideal_height / request.multiple))
    best = None
    for width_index in width_candidates:
        for height_index in height_candidates:
            score = _candidate_score(
                width_index,
                height_index,
                request.multiple,
                target_pixels,
                oriented_ratio,
                native_width_index,
                native_height_index,
            )
            if best is None or score < best[0]:
                best = (score, width_index, height_index)
    if best is None:
        _raise_error("invalid_numeric")
    _score, width_index, height_index = best
    width = width_index * request.multiple
    height = height_index * request.multiple
    if min(width, height) < 1 or max(width, height) > MAX_DIMENSION:
        _raise_error("invalid_dimension_bound")
    actual_megapixels = width * height / PIXEL_UNIT
    realized_aspect_ratio = width / height
    pixel_error_percent = (width * height / target_pixels - 1) * 100
    aspect_error_percent = (realized_aspect_ratio / oriented_ratio - 1) * 100
    diagnostics = (
        actual_megapixels,
        realized_aspect_ratio,
        pixel_error_percent,
        aspect_error_percent,
    )
    if not all(math.isfinite(value) for value in diagnostics):
        _raise_error("invalid_numeric")
    return ResolutionResult(
        width=width,
        height=height,
        resolved_aspect_ratio=ratio.label,
        resolved_direction=request.direction,
        actual_megapixels=actual_megapixels,
        pixel_error_percent=pixel_error_percent,
        realized_aspect_ratio=realized_aspect_ratio,
        aspect_error_percent=aspect_error_percent,
    )
