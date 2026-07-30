# Image Cropper

Crops an image batch by fixed length and aspect ratio, optionally centers the crop
from a mask, and can resize the cropped result.

## Inputs

- `image`: Image batch to crop.
- `enable_fixed_crop`: Derives the crop from a fixed side length before ratio fitting.
- `fixed_crop_side`: Dimension controlled by `fixed_crop_length`.
- `fixed_crop_length`: Target length for the selected fixed side.
- `aspect_ratio`: Crop rectangle ratio; `custom` uses the proportional values.
- `proportional_width`: Width component of a custom ratio.
- `proportional_height`: Height component of a custom ratio.
- `alignment`: Base crop placement when no mask center is used.
- `offset_x`: Horizontal offset from the calculated crop center.
- `offset_y`: Vertical offset from the calculated crop center.
- `scale_to_side`: Optional output dimension resized to `scale_to_length`.
- `scale_to_length`: Target length for the selected resize policy.
- `interpolation_mode`: Sampling method used when resizing.
- `mask`: Optional mask whose nonzero bounding-box center guides crop placement.

## Behavior

The crop rectangle is constrained to the source image. A supplied mask can guide the
center independently for each batch item; alignment and offsets determine the
remaining placement. Resizing happens after cropping and does not produce a separate
mask output.
