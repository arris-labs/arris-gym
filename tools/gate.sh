#!/usr/bin/env bash
# The gate (.agents/rules/git.md): every stage runs, and the last lines name
# each red one. Run by .githooks/pre-commit and by CI's `test` matrix. Offline
# once the environment is synced: no stage fetches a corpus.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
red=()
stage() {
  local name=$1; shift
  echo "gate: $name"
  "$@" || red+=("$name")
}
stage lock uv lock --check --quiet
stage layers uv run --locked tools/check_layers.py
stage fixtures tools/check-fixtures.sh
stage bash-guard tools/bash-guard-test.sh
stage arris-api uv run --locked tools/gen_arris_api.py --check
stage ruff-format uv run --locked ruff format --check --quiet
stage ruff-lint uv run --locked ruff check --quiet
stage mypy uv run --locked mypy
stage pytest uv run --locked pytest
if [ ${#red[@]} -gt 0 ]; then
  echo "gate: RED: ${red[*]}" >&2
  exit 1
fi
echo "gate: green"
