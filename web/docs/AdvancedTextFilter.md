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

### Missing-match policy

For operations that search for a pattern or boundary, the policy is independent of
the operation family:

- `return original text`: output 0 is the preprocessed input and output 1 is empty.
- `return empty string`: output 0 is empty and output 1 is the preprocessed input.
- `trigger error`: raises an intentional node error with a safe static reason.

Concatenation and case conversion are applied before matching. The preprocessed input
therefore includes the selected `concat_mode` and `case_conversion` result.

### First-match boundaries

For `LEFT<MARK>RIGHT`, the boundary operations assign the marker as follows:

- `extract before start text` returns `LEFT` and `<MARK>RIGHT`.
- `remove before start text` returns `<MARK>RIGHT` and `LEFT`.
- `extract after start text` returns `RIGHT` and `LEFT<MARK>`.
- `remove after start text` returns `LEFT<MARK>` and `RIGHT`.

`extract between` and `remove between` preserve both boundary markers on their
remaining side.

### LLM utilities

`LLM: extract JSON object ({...})` scans for the first valid JSON object, skips
malformed candidates, rejects arrays, scalars, and non-standard numeric constants,
and inspects at most 1,024 brace candidates. The remaining output preserves all
text outside the selected object.

`LLM: extract code block (```)` removes the complete opening info line, including
punctuation-bearing language names such as `c++` and `objective-c`. Unlabeled,
CRLF, inline, multiple, and unmatched fences follow the same two-output contract.

`LLM: clean markdown formatting` removes supported formatting delimiters while
preserving literal underscores inside identifiers such as `snake_case`.
