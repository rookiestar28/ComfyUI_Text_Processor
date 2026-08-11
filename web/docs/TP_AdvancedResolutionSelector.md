# Advanced Resolution Selector

## Inputs

- `output_mode` chooses `fixed`, `randomize`, or `randomize_all`.
- `aspect_ratio` selects one of the canonical ratios `1:1`, `9:7`, `4:3`,
  `19:13`, `3:2`, `7:4`, `16:9`, `21:9`, or `custom`.
- `direction` selects `landscape` or `portrait` for fixed mode. Randomized
  modes resolve direction from the seeded stream.
- `custom_ratio_width` and `custom_ratio_height` define a positive custom ratio
  when `aspect_ratio` is `custom`. They are validated for every mode.
- `megapixels` is a binary `1024 * 1024` target area from `0.1` through `16.0`.
- `multiple` aligns both dimensions to a valid positive multiple from `8` through
  `128`.
- `seed` is an unsigned 32-bit integer used for reproducible randomized modes.

## Behavior

`fixed` uses the selected ratio and direction without consuming a random draw.
`randomize` keeps the selected or custom ratio and consumes one seeded direction
draw. `randomize_all` validates the custom fields, then consumes one seeded
canonical-ratio draw followed by one seeded direction draw; the custom sentinel
is never a candidate in this mode.

The node uses an isolated seeded stream and does not change the process-global
random generator. Identical serialized inputs produce identical results. The
calculation preserves Python's ties-to-even rounding while selecting a bounded
aligned candidate that balances area and aspect-ratio error. Alignment can make
the realized area or ratio differ from the target; the final diagnostics expose
those signed differences.

Outputs are `width`, `height`, `resolved_aspect_ratio`, `resolved_direction`,
`actual_megapixels`, `pixel_error_percent`, and `aspect_error_percent`.

After a successful execution, the optional frontend extension shows the final
multiple-aligned values beside the `width` and `height` output ports as
`width: N` and `height: N`. These labels describe the last successful result;
they do not predict edits that have not been queued and remain unchanged after
a failed or unrelated execution. If the extension is unavailable, the node
continues to compute and expose all seven outputs with its static labels.
