# Resize Image Advanced

Resizes image batches with explicit dimensions or aspect-ratio target calculation,
multiple fit policies, optional mask alignment, and selectable processing methods.

## Inputs

- `image`: Image batch to resize.
- `resize_mode`: Uses explicit dimensions or calculates a target from ratio controls.
- `width`: Explicit output width; zero derives width from height and source ratio.
- `height`: Explicit output height; zero derives height from width and source ratio.
- `aspect_ratio`: Target ratio in ratio mode; `custom` uses proportional values.
- `proportional_width`: Width component of a custom ratio.
- `proportional_height`: Height component of a custom ratio.
- `fit`: Controls stretching, fitting, padding, cropping, or pixel-budget behavior.
- `method`: Resize algorithm. `nvidia_rtx_vsr` requires a compatible NVIDIA runtime.
- `scale_to_side`: Dimension or total-pixel policy controlled by
  `scale_to_length`.
- `scale_to_length`: Target side length, or kilo-pixel budget in total-pixel mode.
- `background_color`: Hex fill color for letterbox and padding modes.
- `crop_position`: Anchor used when crop fitting removes overflow.
- `round_to_multiple`: Rounds final dimensions to a multiple; zero disables rounding.
- `device`: Requested processing device, subject to method and runtime availability.
- `mask`: Optional mask transformed with the same geometry as the image.

## Behavior

The node returns the resized image, final width, final height, and an aligned mask.
When no mask is connected, the mask output uses the node's documented empty-mask
fallback. Fit and rounding policies are applied deterministically to the whole batch.
Device-specific methods fail clearly when their required runtime is unavailable.
