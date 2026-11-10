#!/usr/bin/env python3
"""Compare two `rescore.json` files: the rows that differ, and where each first differs.

plans/m5-rescore step 8. `arris-gym rescore benchcad` on two machines gives
tables whose digests should be equal; when they are not, this names the rows
and the first stage of the pipeline each one differs at, so a difference can
be shrunk to a fixture. Reads the JSON as data, never runs a program.

    tools/rescore_diff.py A.json B.json

Exit 0 when the tables are equal, 1 on any difference (a row, a row present in
one table only, or an aggregate), 2 on a file it cannot read.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Callable, Sequence
from typing import Any, Final

EXIT_DIFFERENT: Final = 1
EXIT_UNREADABLE: Final = 2

Row = dict[str, Any]


def _pinned(versions: dict[str, str]) -> dict[str, str]:
    """`versions` without arris-gym's own: a release bump is not a difference (ADR-0011)."""
    return {key: value for key, value in versions.items() if key != "arris_gym"}


# The pipeline's order: a row is blamed on the first of these that differs, so
# an upstream difference (the program, its body, the target) is named before the
# terms it moves.
STAGES: Final[tuple[tuple[str, Callable[[Row], Any]], ...]] = (
    ("program", lambda r: (r["program_sha256"], r["program_status"], r["program_refusal"])),
    ("candidate body", lambda r: r["candidate_sha256"]),
    ("target STEP", lambda r: r["step_sha256"]),
    ("target body", lambda r: r["target_sha256"]),
    ("iou route", lambda r: r["score"]["iou_route"]),
    ("iou", lambda r: r["score"]["iou"]),
    ("surface", lambda r: r["score"]["surface"]),
    ("measures", lambda r: r["score"]["measures"]),
    ("topology", lambda r: r["score"]["topology"]),
    ("field metrics", lambda r: r["score"]["field"]),
    ("reward", lambda r: r["score"]["reward"]),
    ("status", lambda r: (r["stage"], r["score"]["status"], r["score"]["message"])),
    (
        "versions",
        lambda r: (
            _pinned(r["versions"]),
            _pinned(r["score"]["versions"]),
            r["score"]["reward_version"],
        ),
    ),
)
"""Each stage: its name and what of a row it compares, in pipeline order."""

AGGREGATES: Final = (
    "programs",
    "statuses",
    "stages",
    "iou_routes",
    "invalidity_rate",
    "mean_reward",
    "valid",
    "mean_reward_valid",
    "timed_out",
    "digest",
)


def _unversioned(row: Row) -> Row:
    """`row` with arris-gym's own version removed, as the stages compare it."""
    return {
        **row,
        "versions": _pinned(row["versions"]),
        "score": {**row["score"], "versions": _pinned(row["score"]["versions"])},
    }


def first_difference(a: Row, b: Row) -> str | None:
    """The name of the first stage at which rows `a` and `b` differ, None when they do not."""
    for name, pick in STAGES:
        if pick(a) != pick(b):
            return name
    return None if _unversioned(a) == _unversioned(b) else "other fields"


def diff(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """The lines describing every difference of two tables; empty when equal."""
    rows_a = {row["name"]: row for row in a["rows"]}
    rows_b = {row["name"]: row for row in b["rows"]}
    lines: list[str] = []
    for name in sorted(rows_a.keys() | rows_b.keys()):
        if name not in rows_b:
            lines.append(f"{name}: only in A")
        elif name not in rows_a:
            lines.append(f"{name}: only in B")
        elif (stage := first_difference(rows_a[name], rows_b[name])) is not None:
            lines.append(f"{name}: first differs at {stage}")
    lines += [f"aggregate {key} differs" for key in AGGREGATES if a.get(key) != b.get(key)]
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Compare the two files, print the differences and the counts; the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("a", type=pathlib.Path)
    parser.add_argument("b", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        tables = [json.loads(path.read_text(encoding="utf-8")) for path in (args.a, args.b)]
        lines = diff(*tables)
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"rescore_diff: cannot compare: {err!r}", file=sys.stderr)
        return EXIT_UNREADABLE
    for line in lines:
        print(line)
    print(f"{len(lines)} differences" if lines else "equal")
    return EXIT_DIFFERENT if lines else 0


if __name__ == "__main__":
    sys.exit(main())
