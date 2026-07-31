# Global Random Seed

Applies one bounded seed across recognized literal seed inputs in the submitted
prompt without requiring workflow connections.

## Inputs

- `value`: Current seed stored as an exact unsigned decimal string.
- `seed_width`: Uses `uint32` by default for consumers limited to
  `0..4294967295`; `uint64` is an explicit opt-in up to
  `18446744073709551615`.
- `timing`: Applies the queue action before this generation or advances it after
  this generation.
- `queue_action`: Keeps, increments, decrements, or randomizes the controller
  value.
- `distribution`: Reuses, increments, decrements, or independently randomizes one
  seed per target node.
- `last_seed`: Exact decimal readback of the seed applied to the latest submitted
  prompt.

## Behavior

The lowest controller node ID is authoritative when a prompt contains multiple
controllers. Target nodes are processed in stable node-ID order. Only literal
integer inputs named `seed`, `noise_seed`, or `seed_num` are changed; links,
booleans, non-integers, and unrelated inputs are preserved.

Prompt assignment is performed by the backend and does not require serialized
workflow metadata or an open browser. Browser readback uses exact decimal strings.
Target widgets are synchronized only when the assigned value is exactly safe as a
JavaScript number; an unsafe `uint64` target widget is left unchanged instead of
being rounded.
