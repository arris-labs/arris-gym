#!/usr/bin/env bash
# A fixture's expectation is not loosened to pass (.agents/rules/gym.md,
# "Every failure becomes a fixture"). Run by the gate; red when an
# `expected.json` outside tests/fixtures/regression/ carries a "tolerance"
# key and its fixture directory has no README.md citing the ADR that decided
# it. A regression fixture may name one: it records the desired assertion.
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
status=0
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
