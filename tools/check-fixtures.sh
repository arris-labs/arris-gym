#!/usr/bin/env bash
# A fixture's expectation is not loosened to pass (.agents/rules/gym.md,
# "Every failure becomes a fixture"). Run by the gate; red when an
# `expected.json` outside tests/fixtures/regression/ carries a "tolerance"
# key and its fixture directory has no README.md citing the ADR that decided
# it. A regression fixture may name one: it records the desired assertion.
# Also red when a docstring under src/ cites a fixture slug (`ok-…`,
# `runtime-…`, `unsupported-…`) that has no directory under tests/fixtures: a
# claim in prose is backed by the fixture that proves it (plans/lift-holes-and-points
# review). ADRs are append-only and may name fixtures that were since renamed.
# Also red when an `expected.json` declares its message per machine
# ("message_by_machine") and its fixture directory has no README.md saying why.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
bad=()
while IFS= read -r f; do
  dir=$(dirname "$f")
  if ! grep -qsE 'ADR-[0-9]{4}' "$dir/README.md"; then
    bad+=("$f")
  fi
done < <(grep -rlEs '"tolerance"[[:space:]]*:' tests/fixtures --include=expected.json \
           | grep -v '^tests/fixtures/regression/' | sort)
per_machine=()
while IFS= read -r f; do
  [ -s "$(dirname "$f")/README.md" ] || per_machine+=("$f")
done < <(grep -rlEs '"message_by_machine"[[:space:]]*:' tests/fixtures --include=expected.json | sort)
cited=()
while IFS= read -r slug; do
  [ -n "$(find tests/fixtures -type d -name "$slug" -print -quit)" ] || cited+=("$slug")
done < <(grep -rhoE '`(ok|runtime|unsupported)-[a-z0-9-]+`' src --include=*.py | tr -d '`' | sort -u)
status=0
if [ ${#cited[@]} -gt 0 ]; then
  echo "check-fixtures: a docstring under src/ cites a fixture that does not exist:" >&2
  printf '  %s\n' "${cited[@]}" >&2
  status=1
fi
if [ ${#bad[@]} -gt 0 ]; then
  echo "check-fixtures: a tolerance key outside regression/ needs a README.md citing its ADR;" >&2
  echo "  a case that fails at the default is an xfail regression fixture instead:" >&2
  printf '  %s\n' "${bad[@]}" >&2
  status=1
fi
if [ ${#per_machine[@]} -gt 0 ]; then
  echo "check-fixtures: a message per machine needs a README.md saying why it differs:" >&2
  printf '  %s\n' "${per_machine[@]}" >&2
  status=1
fi
exit $status
