#!/usr/bin/env python3
"""Rerun a table's in-subset `cq_bug` programs and retain their messages verbatim.

No oracle is imported or run. The pinned BenchCAD corpus needs the `[corpus]`
extra and its Hugging Face cache or network; this command stays outside the gate:

    uv run --extra corpus tools/cq_diagnose.py

The output has no program text or wall-clock fields. Rows are sorted by stem;
the histogram is sorted by descending count, then message. Membership is decided
statically, before any program runs, as ADR-0012 requires.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import arris_gym as ag
from arris_gym.census import CorpusProgram, benchcad, reach
from arris_gym.cq import subset
from arris_gym.fidelity import DisagreementClass, FidelityTable

C2 = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "c2" / "benchcad"
# Same per-program backstop used by cq_corpus.py; no oracle runs here.
TIMEOUT = 30.0
WORKERS = 8


class _Row(TypedDict):
    stem: str
    family: str
    source: str
    licence: str
    program_sha256: str
    status: str
    message: str
    versions: dict[str, str]


class _Cause(TypedDict):
    message: str
    programs: int
    families: dict[str, int]


class _Diagnosis(TypedDict):
    table_digest: str
    corpus_programs: int
    in_subset: int
    diagnosed: int
    histogram: list[_Cause]
    rows: list[_Row]


def diagnose(
    table: FidelityTable,
    programs: Sequence[CorpusProgram],
    *,
    workers: int = WORKERS,
    timeout: float = TIMEOUT,
) -> _Diagnosis:
    """Rerun every statically in-subset `cq_bug` row, preserving status and message.

    Refuses duplicate stems, missing or extra programs and a program whose text
    hash differs from its table row. Every selected program has one output row,
    including a timeout or crash; no status is inferred from message wording.
    Input order cannot change the output's order. Program text runs only through
    `Sandbox.run_many`, never in this process.
    """
    entries = {entry.name: entry for entry in table.entries}
    by_name = {p.stem: p for p in programs}
    if len(by_name) != len(programs):
        raise ValueError("duplicate program stems")
    if sorted(entries) != sorted(by_name):
        raise ValueError("table and programs must have exactly the same stems")
    for name, program in sorted(by_name.items()):
        if (
            hashlib.sha256(program.text.encode("utf-8")).hexdigest()
            != entries[name].row.program_sha256
        ):
            raise ValueError(f"{name}: program text differs from the table's hash")
    admitted = reach(programs, subset())
    chosen = [
        by_name[name]
        for name in admitted.stems
        if entries[name].row.disagreement is DisagreementClass.CQ_BUG
    ]
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(
            [p.text for p in chosen], dialect="cq", timeout=timeout, workers=workers
        )
    rows: list[_Row] = []
    for program, result in zip(chosen, results, strict=True):
        entry = entries[program.stem]
        if result.program_sha256 != entry.row.program_sha256:
            raise ValueError(f"{program.stem}: sandbox returned another program's result")
        rows.append(
            {
                "stem": program.stem,
                "family": program.family,
                "source": entry.source,
                "licence": entry.licence,
                "program_sha256": result.program_sha256,
                "status": result.status.value,
                "message": result.message,
                "versions": {
                    "arris": result.versions.arris,
                    "numpy": result.versions.numpy,
                    "arris_gym": result.versions.arris_gym,
                },
            }
        )
    counts = Counter(result.message for result in results)
    histogram: list[_Cause] = [
        {
            "message": message,
            "programs": count,
            "families": dict(
                sorted(
                    Counter(
                        p.family
                        for p, r in zip(chosen, results, strict=True)
                        if r.message == message
                    ).items()
                )
            ),
        }
        for message, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "table_digest": table.digest,
        "corpus_programs": table.programs,
        "in_subset": admitted.in_subset,
        "diagnosed": len(rows),
        "histogram": histogram,
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Diagnose the pinned BenchCAD table and write its messages, without program text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, default=C2 / "fidelity.json.gz")
    parser.add_argument("--out", type=Path, default=C2 / "cq-bugs.json")
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    args = parser.parse_args(argv)
    table = FidelityTable.from_json(gzip.decompress(args.table.read_bytes()).decode("utf-8"))
    report = diagnose(table, benchcad.read(), workers=args.workers, timeout=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{report['diagnosed']} in-subset cq_bug programs diagnosed")
    for cause in report["histogram"]:
        print(f"{cause['programs']}: {cause['message']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
