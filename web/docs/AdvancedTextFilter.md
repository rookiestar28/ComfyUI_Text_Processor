# Advanced Text Filter

Filters, extracts, replaces, or cleans text with explicit handling for missing
matches. Use it for prompt cleanup, structured-output extraction, and repeatable
find/replace pipelines.

## Inputs

- `text`: Primary text processed by the selected operation.
- `concat_mode`: Optionally prepends or appends `external_text` before processing.
- `operation`: Selects the filtering, extraction, replacement, or cleanup behavior.
- `start_text`: Opening marker for between, before, and after operations.
- `end_text`: Closing marker for operations that use a bounded range.
- `optional_text_input`: Search text or comma-separated patterns for find operations.
- `replace_with_text`: Replacement value for find-and-replace.
- `use_regex`: Treats supported search or boundary values as regular expressions.
- `case_conversion`: Optionally changes the processed target to upper or lower case.
- `if_not_found`: Returns the original text, an empty string, or an error when no
  requested match exists.
- `external_text`: Optional upstream value combined according to `concat_mode`.
- `replacement_rules`: One `find_text -> replace_text` rule per line for batch
  replacement.

## Behavior

The first output is the processed target. The second output contains remaining or
match-context text when the selected operation produces it. Regular-expression mode
uses the supplied patterns directly, so test complex expressions with representative
input and select an appropriate `if_not_found` policy.
