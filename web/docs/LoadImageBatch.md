# Load Image Batch

Loads a single image from a validated directory batch using fixed-index,
incremental, or seeded-random selection.

## Inputs

- `mode`: Selects fixed index, per-label incremental state, or deterministic random
  choice.
- `seed`: Seed used by random mode.
- `index`: Zero-based position used by single-image mode.
- `label`: State key that keeps different incremental loaders independent.
- `path`: Directory containing the batch.
- `pattern`: Filename glob applied inside the directory; traversal and nested path
  patterns are rejected.
- `allow_RGBA_output`: Preserves alpha when present instead of returning RGB only.
- `filename_text_extension`: Includes or removes the extension in the filename output.

## Behavior

Only supported static image files that match `pattern` are considered. Incremental
mode advances independently for each `label` and wraps within the current file list.
Random mode uses `seed` for repeatable selection. The outputs are the decoded image
tensor and selected filename text.
