# Text Storage (Reader)

Reads a named entry from the persistent Text Storage area.

## Inputs

- `text_key`: Saved Text Storage entry to read.

## Behavior

The dropdown is refreshed from the available JSON and text entries. Selecting the
empty-state placeholder returns an empty string. Changes written by the companion
writer invalidate the reader so the available keys and content can refresh.
