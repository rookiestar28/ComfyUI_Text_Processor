# Advanced Image Saver (Aesthetic)

Saves image batches with flexible naming, metadata controls, previews, and optional
aesthetic-score filtering.

## Inputs

- `images`: Image batch to save and optionally filter.
- `output_path`: Output subfolder or an explicitly allowed absolute directory; time
  placeholders may be used.
- `allow_absolute_output_path`: Allows destinations outside the normal output root.
  Leave this disabled unless the destination is trusted.
- `filename_prefix`: Base filename before the generated number.
- `filename_delimiter`: Separator between the prefix and number.
- `filename_number_padding`: Minimum digit width of generated numbers.
- `filename_number_start`: Places the generated number before the prefix.
- `extension`: Output image format.
- `dpi`: DPI metadata for formats that support it.
- `quality`: Encoder quality for applicable formats.
- `optimize_image`: Requests supported encoder optimization.
- `lossless_webp`: Enables lossless WebP encoding.
- `overwrite_mode`: Uses numbered files or a filename derived from the prefix.
- `embed_workflow`: Embeds available workflow metadata where supported.
- `show_previews`: Returns contained output previews to the UI.
- `metadata_mode`: Writes full, minimal, or no available generation metadata.
- `calculate_aesthetic_score`: Runs the optional local aesthetic model and filters by
  threshold.
- `allow_aesthetic_remote_code`: Permits model-repository code for aesthetic scoring.
  Enable only when the source is trusted.
- `aesthetic_precision`: Chooses the model device and numeric precision policy.
- `keep_aesthetic_model_loaded`: Retains the optional model between executions.
- `aesthetic_threshold`: Minimum score required for an image to be saved.
- `aesthetic_score`: Optional upstream score text used instead of local scoring.

## Behavior

Images that meet the active scoring policy are saved and returned through
`filtered_images`. `files` reports saved paths and `scores` reports score values or
diagnostics. Preview entries are emitted only for destinations that can be represented
inside the normal output route. Model scoring requires the optional aesthetic
dependency and can consume substantial device memory when kept loaded.
