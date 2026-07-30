# Add text to image

Renders labels on an image batch with configurable anchors, colors, backgrounds,
wrapping, shrinking, and truncation.

## Inputs

- `image`: Image batch on which labels are rendered.
- `font_name`: Font family used for every label.
- `text_position`: Anchor for the text block and background.
- `background_mode`: Uses a fitted text box or a strip across the image width.
- `font_size`: Initial font size in pixels.
- `margin`: Distance between the anchored text block and image edge.
- `line_spacing`: Additional spacing between wrapped lines.
- `text_color_hex`: Text color in `#RRGGBB` or `#RRGGBBAA` form.
- `background_color_hex`: Background color in `#RRGGBB` or `#RRGGBBAA` form.
- `background_padding`: Space between text and the background boundary.
- `auto_adapt`: Wraps and shrinks text to fit; when disabled, overflow is truncated.
- `min_font_size`: Smallest font size allowed while adapting.
- `label_text`: Newline-separated labels assigned across the image batch.

## Behavior

Each image receives a label from `label_text`. Adaptive mode searches for a size and
line layout that fits the available area without shrinking below `min_font_size`.
Color alpha controls transparency. The output remains an image batch with the
rendered overlays.
