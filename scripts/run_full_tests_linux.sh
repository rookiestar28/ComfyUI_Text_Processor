#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

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
