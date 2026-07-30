# Text Storage (Writer)

Adds, overwrites, or deletes persistent text entries and returns the input text for
downstream use.

## Inputs

- `text_input`: Text to store and pass through. Delete mode ignores its content.
- `filename_prefix`: Optional prefix placed before the entry name.
- `save_name`: Logical name of the entry to change.
- `mode`: Adds with automatic collision-safe renaming, overwrites the named entry, or
  deletes it.
- `storage_format`: Uses the JSON collection or an individual text file.

## Behavior

Text Storage prefers the active ComfyUI user area and can read legacy entries as a
fallback. Add mode preserves an existing name by choosing a new one. Overwrite and
Delete target the composed name directly. The output is always the original
`text_input`.
