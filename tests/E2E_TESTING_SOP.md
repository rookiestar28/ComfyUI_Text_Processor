# E2E Testing SOP

This SOP defines the ComfyUI custom-node smoke/integration workflow for **ComfyUI Text Processor**.

## Scope

This is not a frontend Playwright workflow.

This repository is a Python ComfyUI custom node pack, so the E2E boundary is:

- ComfyUI can discover and import the node package.
- `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` expose expected nodes.
- Changed node classes can execute representative workflows with deterministic inputs.
- Output tensor/string/file contracts match the node definitions.

## Problem-First Test Design Rule

E2E scripts and mocked harness flows must be designed to reproduce failures and catch bugs early. The goal is not to make the harness pass; the goal is to make the harness fail when a real user-facing contract breaks.

When adding or reviewing E2E coverage, prefer assertions that prove final user-visible behavior, request routing, payload shape, state synchronization, and failure feedback. Avoid pass-only checks that only prove the page loaded or a mocked happy path returned.
## Requirements

- Python 3.10+ in the same environment used by ComfyUI.
- ComfyUI dependencies importable in that environment, including `folder_paths`.
- For image/tensor nodes: `torch`, `torchvision`, `Pillow`, and `numpy`.
- For text scraper checks: mockable `requests` and `beautifulsoup4`.
- No Node.js or npm requirement exists unless a tracked frontend harness is added later.

## Windows Procedure

Use the ComfyUI Python environment. Example with conda:

```powershell
conda run -n comfyui python --version
conda run -n comfyui python -c "import torch; print(torch.__version__)"
```

Compile product modules:

```powershell
conda run -n comfyui python -m py_compile `
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

Run focused changed-node assertions.

Example for `Image_concat_advanced.py`:

```powershell
conda run -n comfyui python -c "import torch; from Image_concat_advanced import TP_ImageConcatenateMulti; node = TP_ImageConcatenateMulti(); img = lambda v: torch.full((1, 2, 2, 3), float(v)); out, = node.concatenate([img(1), img(2), img(3)], 'left_to_right', 2, 'nearest', 'rgb'); assert tuple(out.shape) == (1, 4, 4, 3); print('ok')"
```

Run tracked unittest regression tests when present:

```powershell
conda run -n comfyui python -m unittest discover -s tests -p "test_*.py"
```

The tracked unittest suite includes a package registration smoke test using a lightweight `folder_paths` stub. Run it as part of the normal unittest command above.

## Linux / WSL Procedure

Use the Python interpreter that ComfyUI uses.

```bash
python --version
python - <<'PY'
try:
    import torch
    print(torch.__version__)
except Exception as exc:
    print(f"torch unavailable: {exc}")
PY
```

Compile product modules:

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

Run focused changed-node assertions with deterministic inputs.

## Node Registration Smoke

When ComfyUI runtime imports are available, verify node registration:

```powershell
conda run -n comfyui python -c "import importlib.util, pathlib; spec = importlib.util.spec_from_file_location('ComfyUI_Text_Processor', pathlib.Path('__init__.py')); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); print(sorted(module.NODE_CLASS_MAPPINGS.keys()))"
```

If this fails because the package is not being imported from ComfyUI's `custom_nodes` parent, record the import-context limitation and run focused changed-node assertions instead.

For local CI-style validation without a full ComfyUI checkout, use:

```powershell
conda run -n comfyui python -m unittest tests.test_node_registration
```

## Changed-node Assertion Requirements

Each implementation must include assertions matching the changed node type:

- `STRING` nodes: exact output tuple values for normal and edge cases.
- `IMAGE` nodes: tensor shape, dtype/device preservation where relevant, channel count, and content placement.
- `MASK` nodes: mask shape and value range.
- output nodes that write files: isolated path, filename behavior, and metadata behavior where applicable.
- network nodes: mocked success, timeout/error behavior, and blocked unsafe input behavior.

## Non-applicable Frontend E2E

Do not run these commands for the current repo state:

```bash
npm install
npx playwright install chromium
npm test
```

They become applicable only after a tracked frontend harness and `package.json` are added.

## Troubleshooting

- `ModuleNotFoundError: folder_paths`: run from the ComfyUI environment or record that full ComfyUI import smoke is blocked by missing ComfyUI runtime context.
- `ModuleNotFoundError: torch`: use the ComfyUI Python environment for image/tensor node checks.
- `ModuleNotFoundError` for optional dependencies: record whether the changed node requires the optional dependency or is expected to degrade gracefully.
- Very large image grids can allocate large tensors; use tiny deterministic tensors for automated assertions.

## Evidence Recording

Record:

- exact Python executable
- Python version
- relevant package versions
- commands run
- assertion coverage summary
- final pass/fail/blocked status
<!-- ROOKIEUI-GLOBAL-E2E-SOP-RULES:START -->
## RookieUI-Derived Global E2E Rules

This section preserves the repo's existing E2E procedure while adding the shared Playwright/harness baseline used across this workspace.

### Problem-First Test Design Rule

E2E scripts and mocked harness flows must be designed to reproduce failures and catch bugs early. The goal is not to make the harness pass; the goal is to make the harness fail when a real user-facing contract breaks.

When adding or reviewing E2E coverage, prefer assertions that prove final user-visible behavior, request routing, payload shape, state synchronization, and failure feedback. Avoid pass-only checks that only prove the page loaded or a mocked happy path returned.

### Requirements

- Node.js 18+
- npm 9+ when the repo uses npm
- Python command available (`python` or a local shim to `python3`) when the harness serves files through Python
- Playwright Chromium installed with `npx playwright install chromium` when Playwright is used

### Windows (PowerShell)

```powershell
node -v
npm -v
python --version

npm install
npx playwright install chromium
npm test
```

### WSL2 (bash)

```bash
source ~/.nvm/nvm.sh
nvm use 18
node -v
python3 --version

mkdir -p .tmp/bin
ln -sf "$(command -v python3)" .tmp/bin/python

npm install
npx playwright install chromium

mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright \
  PATH=".tmp/bin:$PATH" npm test
```

### Troubleshooting

- `python: command not found` on WSL: create `.tmp/bin/python` as a shim to `python3`.
- Port bind failure: use the repo-documented E2E port override or stop the conflicting process.
- Browser missing: run `npx playwright install chromium`.
- Dependency drift: remove `node_modules` and rerun `npm install`.

### Non-applicable E2E

If the repo does not have a frontend or Playwright harness, document the non-applicability in `tests/TEST_SOP.md` and identify the replacement smoke, unit, or integration lane. Do not treat a missing E2E harness as an unrecorded pass.
<!-- ROOKIEUI-GLOBAL-E2E-SOP-RULES:END -->
