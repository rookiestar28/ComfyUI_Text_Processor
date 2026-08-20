# Test SOP

<!-- CURRENT-TEST-GOVERNANCE:START -->
## Current Change-Governance Authority

This section supersedes narrower documentation exceptions, platform-selection rules, and Hosted CI
acceptance wording elsewhere in this file.

- Pure text/documentation changes and version-field-only `pyproject.toml` updates do not require
  planning, a roadmap item, records/logs, independent review, a documentation test contract, E2E,
  or the full repository gate. Use proportionate text/TOML/metadata checks only when useful.
- Dependency, build, tool-configuration, entry-point, runtime-compatibility, or other
  behavior-bearing `pyproject.toml` changes are not version-only fast-path changes.
- For non-exempt work, a passing Windows Full Gate is the authoritative repository-wide test
  result. Neither push nor Hosted CI is required, and acceptance evidence does not need to bind to a
  pushed commit. Hosted CI is always optional supplemental diagnostics. Linux/WSL runs are optional
  unless the current item explicitly requires platform-specific evidence.
- Required item-scoped security, live-host, provider, migration, release, or publication checks
  remain additive.
<!-- CURRENT-TEST-GOVERNANCE:END -->

This document is the source-of-truth local verification workflow for **ComfyUI Text Processor**.

## Repository Facts

- This repository is a ComfyUI custom node pack with Python runtime nodes and a
  tracked frontend browser-test harness.
- Node entrypoint: `__init__.py`.
- Registered node modules live as root-level `.py` files.
- Runtime frontend extensions live in `web/global_random_seed.js` and
  `web/advanced_resolution_selector.js`.
- `package.json` and Playwright provide mandatory frontend contract/E2E validation.
- The foundational harness does not itself add product runtime JavaScript; every
  frontend extension introduced later enters this same lane.
- `reference/` contains reference material only and is ignored; it is not part of the product validation target.
- `.pre-commit-config.yaml` is present and defines local `detect-secrets` and Python compile hooks.

## Repository-specific E2E Policy

The project-level `AGENTS.md` and this SOP define the same repository-specific gate.
Every change outside the text/version-only-`pyproject.toml` fast-path must run both:

- the Python ComfyUI custom-node smoke/integration lane; and
- the Node.js 18+ Playwright lane through `npm test`.

Use repo-local ignored npm, browser, and temp paths as defined by the full-test
scripts and `tests/E2E_TESTING_SOP.md`.

## Required Reading Order

1. `tests/TEST_SOP.md`
2. `tests/E2E_TESTING_NOTICE.md`
3. `tests/E2E_TESTING_SOP.md`

## Acceptance Rule

A change is not accepted until required checks pass and evidence is recorded.

### Problem-First Test Design Rule (Mandatory)

All test scripts, test harnesses, and validation flows must be designed first to reproduce real failures and catch bugs early.

The purpose of testing is to expose defects, regressions, drift, and broken assumptions before users hit them. Tests must not be designed merely to produce a green validation result, satisfy a checklist, or prove that a happy path still passes. Do not waste validation time on pass-only checks that cannot fail for the bug class under review.

Every bugfix or high-risk change must start from the question: "Which test would have caught this before release?" If the existing gate missed the bug, update the targeted test or SOP flow so the same class of bug fails deterministically next time.
Required gate for this repository:

1. Secret scan: `pre-commit run detect-secrets --all-files`
2. Pre-commit hooks: `pre-commit run --all-files --show-diff-on-failure`
3. Python compile/import smoke checks for tracked product modules
4. Focused unit or tensor behavior checks for changed nodes
5. ComfyUI custom-node smoke/integration lane per `tests/E2E_TESTING_SOP.md`
6. Node.js 18+ frontend/browser lane through `npm test`

## Text And Version-Only `pyproject.toml` Fast-Path

If all tracked changes are pure text/documentation files, a version-field-only
`pyproject.toml` update, or both, the change does not enter the mandatory full-gate
workflow and requires no prior plan, roadmap item, implementation record, command
log, or independent review.

Use proportionate checks:

1. confirm the touched-file set qualifies for the fast-path
2. for text, run readability/format/link checks such as `git diff --check` where useful
3. for a version-field-only `pyproject.toml` update, parse TOML or read back the
   version directly when useful

A version-field-only `pyproject.toml` update does not require Python compilation, the
full unit suite, npm installation/audit, or Playwright. Dependency, build,
tool-configuration, entry-point, packaging, or runtime-semantic changes in that file
are behavior-bearing and use the normal required gate. The normal gate also applies
if product code, tests, executable scripts, generated runtime artifacts, or other
behavior-bearing files change.

## Prerequisites

- Python 3.10+ in the same environment used by ComfyUI, or a repo-local venv with equivalent dependencies.
- For tensor/image node checks: `torch`, `torchvision`, `Pillow`, and ComfyUI runtime dependencies must be importable.
- For optional scraper checks: `requests` and `beautifulsoup4`.
- For optional aesthetic scorer checks: `aesthetic-predictor-v2-5`.
- `pre-commit` only after `.pre-commit-config.yaml` exists.
- Node.js 18+ and npm.
- Playwright Chromium installed in the repo-local ignored browser path.

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
split_string.py
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
load_image_batch.py
resize_image_advanced.py
global_random_seed.py
advanced_resolution_selector_core.py
advanced_resolution_selector.py
```

## One-command Full Test Scripts

Use these scripts for the standard full local gate. They run from the repository root and use the active Python environment unless `PYTHON` / `-Python` is provided.

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Windows with an explicit ComfyUI Python:

```powershell
powershell -File scripts/run_full_tests_windows.ps1 -Python "C:\path\to\python.exe"
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

Linux / WSL with an explicit Python:

```bash
PYTHON=/path/to/python bash scripts/run_full_tests_linux.sh
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
  split_string.py `
  text_scraper.py `
  text_storage.py `
  wildcards.py `
  simple_eval.py `
  add_text_to_image.py `
  font_manager.py `
  advanced_image_saver.py `
  image_cropper.py `
  mask_nodes.py `
  Image_concat_advanced.py `
  load_image_batch.py `
  resize_image_advanced.py
```

Bash:

```bash
python -m py_compile \
  __init__.py \
  advanced_text_filter.py \
  text_input.py \
  split_string.py \
  text_scraper.py \
  text_storage.py \
  wildcards.py \
  simple_eval.py \
  add_text_to_image.py \
  font_manager.py \
  advanced_image_saver.py \
  image_cropper.py \
  mask_nodes.py \
  Image_concat_advanced.py \
  load_image_batch.py \
  resize_image_advanced.py
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

### 6. Frontend Browser Lane

Use repo-local ignored caches and browser binaries:

```powershell
$env:npm_config_cache = (Join-Path (Get-Location) ".tmp/npm-cache")
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location) ".tmp/playwright-browsers")
$env:TMP = (Join-Path (Get-Location) ".tmp/playwright-temp")
$env:TEMP = $env:TMP

node -v
npm ci --ignore-scripts
npx playwright install chromium
npm audit --audit-level=high
npm test
```

## Evidence Recording

Implementation records must include:

- date
- OS and shell
- Python executable and version
- dependency versions relevant to the changed node, such as `torch`
- Node/npm/Playwright versions for frontend validation
- command log or exact commands
- pass/fail/blocked status for every required stage
- reason for any repo-specific override

## Failure Handling

- If a check fails, fix the root cause and rerun the failed check and dependent checks.
- If a check is blocked by missing repository infrastructure, record the blocker and reference the roadmap item that owns the infrastructure gap.
- Do not mark a code change fully accepted while required gate infrastructure is blocked.
<!-- ROOKIEUI-GLOBAL-TEST-SOP-RULES:START -->
## RookieUI-Derived Global Testing Rules

These rules preserve this repository's existing test lanes while adding the shared testing baseline used across this workspace.

### Required Reading Order

1. `tests/TEST_SOP.md`
2. `tests/E2E_TESTING_NOTICE.md`
3. `tests/E2E_TESTING_SOP.md`

### Acceptance Rule

A change is not accepted until required checks pass and evidence is recorded. Existing repo-specific gates remain authoritative; this section adds the shared minimum expectations.

Required shared gate:

1. `pre-commit run detect-secrets --all-files`
2. `pre-commit run --all-files --show-diff-on-failure`
3. backend/unit tests through the repo's documented runner, preferring `scripts/run_unittests.py` when present
4. frontend/E2E tests through the repo's documented Playwright or harness lane, usually `npm test` when a Node harness exists
5. targeted type/static validation when the changed surface has a typed frontend or equivalent static contract

If a repo has no frontend/E2E harness, the SOP must state the non-applicability and identify the replacement smoke, unit, or integration lane that catches the same user-facing risk.

### Problem-First Test Design Rule

All test scripts, test harnesses, and validation flows must be designed first to reproduce real failures and catch bugs early.

The purpose of testing is to expose defects, regressions, drift, and broken assumptions before users hit them. Tests must not be designed merely to produce a green validation result, satisfy a checklist, or prove that a happy path still passes. Do not waste validation time on pass-only checks that cannot fail for the bug class under review.

Every bugfix or high-risk change must start from the question: "Which test would have caught this before release?" If the existing gate missed the bug, update the targeted test or SOP flow so the same class of bug fails deterministically next time.

### Bugfix/Hotfix Rule (Reproduce -> Pin -> Sweep)

For bugfix/hotfix work, acceptance evidence must include:

1. pre-fix reproduction evidence
2. post-fix targeted regression evidence
3. final full-gate evidence

A green full gate alone is not sufficient bugfix evidence unless the record also shows how the specific failure was reproduced and pinned.

### Text And Version-Only `pyproject.toml` Fast-Path

If the complete tracked change set is limited to pure text/documentation files,
a version-field-only `pyproject.toml` update, or both, full test execution is not
required and no planning, roadmap, record, command-log, or independent-review workflow
applies. Validate text lightly and parse or read back the version when useful. If the
TOML edit or any other touched file is behavior-bearing, use the normal gate for the
combined task.

### Environment Guardrails

- Keep the Python interpreter consistent across all commands.
- Prefer a project-local virtual environment: `.venv` on Windows and `.venv-wsl` on WSL/Linux when the repo supports dual-OS validation.
- Do not mix global and venv-installed `pre-commit` accidentally.
- Node.js must be 18+ before running frontend/E2E tests.
- On Windows, prefer repo-local `PRE_COMMIT_HOME` to avoid cache lock issues.
- On WSL, if `python` is missing but `python3` exists, create a local shim before running Playwright or harness commands.
- If pre-commit modifies files, review/stage/commit those changes and rerun hooks until clean.

### Evidence Recording

Implementation records must include date/time, OS/environment, command log reference, and pass/fail result for each required stage. If a gate is intentionally skipped as non-applicable, record why and name the replacement validation lane.
<!-- ROOKIEUI-GLOBAL-TEST-SOP-RULES:END -->
