#!/usr/bin/env python3
"""Run the C1 slice under `cq` and compare each program with the oracle.

Reads the pinned BenchCAD corpus (the `[corpus]` extra; the Hugging Face cache
or the network, outside the gate), runs the slice's programs in the sandbox
under `dialect="cq"`, pairs each result with its report in `oracle.jsonl`,
applies `verdicts.json` (stem -> `Verdict`, optional), and writes the fidelity
table and the arris report (ADR-0006). Every slice program has a row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections.abc import Sequence

import arris_gym as ag
from arris_gym.fidelity import (
    OracleReport,
    TableEntry,
    Verdict,
    arris_rows,
    compare,
    fidelity_table,
)

C1 = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "c1"
# The sandbox's own defaults, which every slice program fitted (step 7 of
# plans/m3-cq-subset measured them).
TIMEOUT = 30.0


def read_slice(path: pathlib.Path) -> list[str]:
    """The stems of a slice file: one per line, `#` lines are its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def read_oracle(path: pathlib.Path) -> dict[str, dict[str, object]]:
    """The rows of an `oracle.jsonl` by stem."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {row["stem"]: row for row in rows}


def read_verdicts(path: pathlib.Path, stems: Sequence[str]) -> dict[str, Verdict]:
    """The verdicts of a `verdicts.json` by stem; none when the file is absent.

    Raises `ValueError` for a verdict on a stem outside the run.
    """
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(raw) - set(stems))
    if unknown:
        raise ValueError(f"verdicts for stems outside the run: {unknown[:5]}")
    return {stem: Verdict.model_validate(value) for stem, value in raw.items()}


def oracle_digest(reports: Sequence[OracleReport]) -> str:
    """The SHA-256 of the reports' own digests, one per line, in the order given."""
    text = "".join(report.digest() + "\n" for report in reports)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the slice (or `--start`:`--stop` of it, sorted by stem) and write the table."""
    from arris_gym.census import benchcad

    parser = argparse.ArgumentParser(description="Run the C1 slice under cq.")
    parser.add_argument("--slice", type=pathlib.Path, default=C1 / "slice.txt")
    parser.add_argument("--oracle", type=pathlib.Path, default=C1 / "oracle.jsonl")
    parser.add_argument("--verdicts", type=pathlib.Path, default=C1 / "verdicts.json")
    parser.add_argument("--out-dir", type=pathlib.Path, default=C1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--workers", type=int)
    args = parser.parse_args(argv)

    stems = sorted(read_slice(args.slice))[args.start : args.stop]
    oracle = read_oracle(args.oracle)
    verdicts = read_verdicts(args.verdicts, stems)
    by_stem = {p.stem: p for p in benchcad.read()}
    missing = [s for s in stems if s not in by_stem or s not in oracle]
    if missing:
        raise ValueError(f"stems the corpus or the oracle lacks: {missing[:5]}")
    programs = [by_stem[s] for s in stems]
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(
            [p.text for p in programs], dialect="cq", timeout=args.timeout, workers=args.workers
        )
    reports = [OracleReport.model_validate(oracle[s]["report"]) for s in stems]
    entries = []
    for program, result, report in zip(programs, results, reports, strict=True):
        if result.program_sha256 != report.program_sha256:
            raise ValueError(f"{program.stem}: the oracle ran another program")
        entries.append(
            TableEntry(
                name=program.stem,
                source=f"{benchcad.REPO}@{benchcad.REVISION}/{benchcad.CONFIG}",
                licence=benchcad.LICENCE,
                row=compare(result, report, verdicts.get(program.stem)),
            )
        )
    table = fidelity_table(entries)
    report_for_arris = arris_rows(table)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "fidelity.json").write_text(table.to_json() + "\n", encoding="utf-8")
    (args.out_dir / "arris-report.json").write_text(
        report_for_arris.to_json() + "\n", encoding="utf-8"
    )
    (args.out_dir / "arris-report.md").write_text(report_for_arris.to_markdown(), encoding="utf-8")
    print(f"{table.programs} programs", file=sys.stderr)
    for key in ("outcomes", "classes", "statuses", "oracle_statuses"):
        print(f"{key}: {getattr(table, key)}", file=sys.stderr)
    print(f"timed out: {list(table.timed_out)}", file=sys.stderr)
    print(f"table digest {table.digest}", file=sys.stderr)
    print(f"oracle digest {oracle_digest(reports)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
