# Test SOP

This document is the source-of-truth local verification workflow for **ComfyUI Text Processor**.

## Repository Facts

- This repository is a Python-only ComfyUI custom node pack.
- Node entrypoint: `__init__.py`.
- Registered node modules live as root-level `.py` files.
- There is no frontend extension, no `package.json`, and no Playwright harness in this repository at the time this SOP was written.
- `reference/` contains reference material only and is ignored; it is not part of the product validation target.
- `.pre-commit-config.yaml` is not present at the time this SOP was written.

## Repository-specific E2E Policy

The project-level `AGENTS.md` and this SOP define the same repository-specific gate.
For this repository, frontend E2E via `npm test` is not applicable unless a tracked frontend harness or `package.json` is added.

Required replacement for the frontend lane:

- run the ComfyUI custom-node smoke/integration lane defined by `tests/E2E_TESTING_SOP.md`.

If an implementation record cites this policy, it must explicitly state:

- no tracked `package.json` exists
- no tracked frontend/E2E harness exists
- `tests/E2E_TESTING_SOP.md` was followed instead

## Required Reading Order

1. `tests/TEST_SOP.md`
2. `tests/E2E_TESTING_NOTICE.md`
3. `tests/E2E_TESTING_SOP.md`

## Acceptance Rule

A change is not accepted until required checks pass and evidence is recorded.

Required gate for this repository:

1. Secret scan: `pre-commit run detect-secrets --all-files`
2. Pre-commit hooks: `pre-commit run --all-files --show-diff-on-failure`
3. Python compile/import smoke checks for tracked product modules
4. Focused unit or tensor behavior checks for changed nodes
5. ComfyUI custom-node smoke/integration lane per `tests/E2E_TESTING_SOP.md`

Current known blocker:

- steps 1 and 2 cannot run until `.pre-commit-config.yaml` exists.
- when blocked, the implementation record must show the attempted command and the exact failure.

## Documentation-only Exception

If all touched files are documentation/planning text only, runtime checks are optional.

Required evidence for documentation-only changes:

1. list touched documentation files
2. confirm no product code, tests, scripts, or config were changed
3. run a lightweight file/readability check where practical

This exception does not apply when any `.py`, packaging, test, script, or runtime config file changes.

## Prerequisites

- Python 3.10+ in the same environment used by ComfyUI, or a repo-local venv with equivalent dependencies.
- For tensor/image node checks: `torch`, `torchvision`, `Pillow`, and ComfyUI runtime dependencies must be importable.
- For optional scraper checks: `requests` and `beautifulsoup4`.
- For optional aesthetic scorer checks: `aesthetic-predictor-v2-5`.
- `pre-commit` only after `.pre-commit-config.yaml` exists.

Recommended interpreter order:

1. active ComfyUI Python environment
2. Windows repo-local `.venv`
3. WSL/Linux repo-local `.venv-wsl`

Do not mix interpreters across gate stages.

## Product Module Set

Unless a task narrows the scope, product Python modules are:

```text
__init__.py
advanced_text_filter.py
text_input.py
text_scraper.py
text_storage.py
wildcards.py
simple_eval.py
add_text_to_image.py
font_manager.py
advanced_image_saver.py
image_cropper.py
mask_nodes.py
Image_concat_advanced.py
```

## Manual Staged Workflow

### 1. Secret scan

```powershell
pre-commit run detect-secrets --all-files
```

If `.pre-commit-config.yaml` is missing, record this as blocked and continue only with the remaining executable checks.

### 2. Pre-commit hooks

```powershell
pre-commit run --all-files --show-diff-on-failure
```

If hooks auto-fix files, review the changes and rerun until clean.

### 3. Python compile check

PowerShell:

```powershell
python -m py_compile `
  __init__.py `
  advanced_text_filter.py `
  text_input.py `
  text_scraper.py `
  text_storage.py `
  wildcards.py `
  simple_eval.py `
  add_text_to_image.py `
  font_manager.py `
  advanced_image_saver.py `
  image_cropper.py `
  mask_nodes.py `
  Image_concat_advanced.py
```

Bash:

```bash
python -m py_compile \
  __init__.py \
  advanced_text_filter.py \
  text_input.py \
  text_scraper.py \
  text_storage.py \
  wildcards.py \
  simple_eval.py \
  add_text_to_image.py \
  font_manager.py \
  advanced_image_saver.py \
  image_cropper.py \
  mask_nodes.py \
  Image_concat_advanced.py
```

### 4. Focused changed-node checks

Run focused Python assertions for every changed node.

Examples:

- text-only nodes: instantiate the node class and assert returned tuples.
- tensor/image nodes: create small deterministic tensors and assert shape, channel count, placement, and edge behavior.
- file I/O nodes: use a temporary directory or isolated fixture path; do not write outside the workspace.
- network nodes: mock network calls unless the task explicitly requires live network verification.

Tracked unittest regression tests, when present:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### 5. ComfyUI custom-node smoke/integration lane

Follow `tests/E2E_TESTING_SOP.md`.

## Evidence Recording

Implementation records must include:

- date
- OS and shell
- Python executable and version
- dependency versions relevant to the changed node, such as `torch`
- command log or exact commands
- pass/fail/blocked status for every required stage
- reason for any repo-specific override

## Failure Handling

- If a check fails, fix the root cause and rerun the failed check and dependent checks.
- If a check is blocked by missing repository infrastructure, record the blocker and reference the roadmap item that owns the infrastructure gap.
- Do not mark a code change fully accepted while required gate infrastructure is blocked.
