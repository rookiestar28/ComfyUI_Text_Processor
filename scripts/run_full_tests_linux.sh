#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$(pwd)/.tmp/pre-commit-cache}"
mkdir -p "$PRE_COMMIT_HOME"
export npm_config_cache="${npm_config_cache:-$(pwd)/.tmp/npm-cache}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$(pwd)/.tmp/playwright-browsers}"
export TMPDIR="${TMPDIR:-$(pwd)/.tmp/playwright-temp}"
export TMP="${TMP:-$TMPDIR}"
export TEMP="${TEMP:-$TMPDIR}"
mkdir -p "$npm_config_cache" "$PLAYWRIGHT_BROWSERS_PATH" "$TMPDIR"

if [[ -n "${PYTHON:-}" ]]; then
  python_cmd="$PYTHON"
elif [[ -x ".venv-wsl/bin/python" ]]; then
  python_cmd=".venv-wsl/bin/python"
elif [[ -x ".venv/bin/python" ]]; then
  python_cmd=".venv/bin/python"
elif [[ -x "$HOME/.conda/envs/comfyui/bin/python" ]]; then
  python_cmd="$HOME/.conda/envs/comfyui/bin/python"
else
  python_cmd="python"
fi

skip_precommit="${SKIP_PRECOMMIT:-0}"

echo
echo "==> Python version"
$python_cmd --version

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 18+ is required for frontend E2E." >&2
  exit 1
fi
node_version="$(node --version)"
node_major="${node_version#v}"
node_major="${node_major%%.*}"
if (( node_major < 18 )); then
  echo "Node.js 18+ is required; active version is $node_version." >&2
  exit 1
fi
echo
echo "==> Node.js version"
echo "$node_version"

if [[ "$skip_precommit" != "1" ]]; then
  echo
  echo "==> detect-secrets"
  $python_cmd -m pre_commit run detect-secrets --all-files

  echo
  echo "==> pre-commit"
  $python_cmd -m pre_commit run --all-files --show-diff-on-failure
fi

echo
echo "==> unit tests"
$python_cmd -m unittest discover -s tests -p "test_*.py"

echo
echo "==> npm clean install"
npm ci --ignore-scripts

echo
echo "==> Playwright Chromium"
npx playwright install chromium

echo
echo "==> npm audit"
npm audit --audit-level=high

echo
echo "==> frontend E2E"
npm test
