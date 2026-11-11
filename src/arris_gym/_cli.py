"""The `arris-gym` command line: `arris-gym census --corpus benchcad [--out DIR]` (ADR-0003).

Parses a corpus and never runs a program; the files it writes are the census
(aggregate and per-program counts, no program text), reach curve and slice stems.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Final

from arris_gym.census import (
    CensusReport,
    CorpusInfo,
    CorpusProgram,
    benchcad,
    cadrecode,
    census,
    census_program,
    reach_curve,
    select_slice,
    slice_families,
)
from arris_gym.cq import subset
from arris_gym.rescore import RescoreTable, rescore
from arris_gym.rescore import benchcad as rescore_benchcad

Reader = Callable[[], list[CorpusProgram]]
"""Reads a corpus's programs; the CLI's seam, so a test needs no download."""

EXIT_USAGE: Final = 2
"""The exit status of a missing `[corpus]` extra, as argparse's own usage errors."""
TOP_ROWS: Final = 10
"""How many ranked families the summary prints."""
SLICE_FAMILIES: Final = 3
"""How many ranked families the slice takes."""
PER_FAMILY: Final = 100
"""How many programs of each (and the fewest a family may have to be eligible)."""
MISSING_EXTRA: Final = "arris-gym needs the corpus extra: pip install 'arris-gym[corpus]'"


def _extra_present() -> bool:
    return all(find_spec(name) is not None for name in ("huggingface_hub", "pyarrow"))


def slice_text(report: CensusReport, stems: Sequence[str]) -> str:
    """The `slice.txt` content: a `#` header naming the corpus and the families, then the stems."""
    corpus = report.corpus
    chosen = slice_families(report, SLICE_FAMILIES, PER_FAMILY)
    header = [
        f"# source: {corpus.source} ({corpus.config})",
        f"# revision: {corpus.revision}",
        f"# licence: {corpus.licence}",
        f"# census digest: {report.digest}",
        f"# families: {', '.join(chosen)}",
    ]
    return "\n".join([*header, *stems, ""])


def run_census(reader: Reader, out: Path, info: CorpusInfo = benchcad.INFO) -> CensusReport:
    """Write census and reach without source text; BenchCAD also gets the C1 slice."""
    programs = reader()
    report = census(programs, info)
    out.mkdir(parents=True, exist_ok=True)
    (out / "census.json").write_text(report.to_json() + "\n", encoding="utf-8")
    if info == benchcad.INFO:
        stems = select_slice(report, programs, SLICE_FAMILIES, PER_FAMILY, PER_FAMILY)
        (out / "slice.txt").write_text(slice_text(report, stems), encoding="utf-8")
    rows = []
    outcomes = []
    for program in sorted(programs, key=lambda p: p.stem):
        outcome = census_program(program)
        outcomes.append(outcome)
        rows.append(
            json.dumps(
                {
                    **report.corpus.model_dump(),
                    "family": program.family,
                    "program_sha256": hashlib.sha256(program.text.encode("utf-8")).hexdigest(),
                    "census": outcome.model_dump(mode="json"),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        )
    data = ("\n".join(rows) + ("\n" if rows else "")).encode("ascii")
    (out / "programs.jsonl.gz").write_bytes(gzip.compress(data, mtime=0))
    (out / "reach.json").write_text(
        reach_curve(outcomes, subset()).to_json() + "\n", encoding="utf-8"
    )
    return report


def run_rescore(
    reader: Reader, slice_path: Path, targets: Path, out: Path, workers: int | None
) -> RescoreTable:
    """Re-score the slice, write `rescore.json` and `rescore.md` into `out`."""
    table = rescore(rescore_benchcad.load(slice_path, targets, reader), workers=workers)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rescore.json").write_text(table.to_json() + "\n", encoding="utf-8")
    (out / "rescore.md").write_text(table.to_markdown(), encoding="utf-8")
    return table


def run_rescore_command(args: argparse.Namespace, reader: Reader) -> int:
    """`arris-gym rescore benchcad`: run it and print the counts and the digest."""
    table = run_rescore(reader, args.slice_path, args.targets, args.out, args.workers)
    print(f"programs {table.programs}")
    print("statuses: " + ", ".join(f"{k} {n}" for k, n in table.statuses.items() if n))
    print("stages: " + ", ".join(f"{k} {n}" for k, n in table.stages.items() if n))
    print(f"invalidity rate {table.invalidity_rate:.6f}")
    print(f"mean reward over all {table.programs} programs: {table.mean_reward:.6f}")
    valid = table.mean_reward_valid
    print(
        f"mean reward over the {table.valid} valid programs only (survivors): "
        + ("none" if valid is None else f"{valid:.6f}")
    )
    print(
        "timed out: "
        + (", ".join(f"{t.name} ({t.stage.value})" for t in table.timed_out) or "none")
    )
    print(f"digest {table.digest}")
    return 0


CORPORA: Final[dict[str, tuple[Reader, CorpusInfo]]] = {
    "benchcad": (benchcad.read, benchcad.INFO),
    "cadrecode": (cadrecode.read, cadrecode.INFO),
}
"""Each census corpus's reader and the source and licence its rows carry."""


def main(argv: Sequence[str] | None = None, *, reader: Reader | None = None) -> int:
    """Run the command; returns the exit status. `reader` replaces the corpus download (tests)."""
    parser = argparse.ArgumentParser(prog="arris-gym")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("census", help="count the API a corpus uses, never running a program")
    cmd.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    cmd.add_argument("--out", type=Path, default=Path("census-out"))
    res = sub.add_parser("rescore", help="re-score a corpus's slice against its committed targets")
    res.add_argument("corpus", choices=["benchcad"])
    res.add_argument("--slice", type=Path, default=rescore_benchcad.SLICE, dest="slice_path")
    res.add_argument("--targets", type=Path, default=rescore_benchcad.TARGETS)
    res.add_argument("--out", type=Path, default=Path("rescore-out"))
    res.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)

    if reader is None:
        if not _extra_present():
            print(MISSING_EXTRA, file=sys.stderr)
            return EXIT_USAGE
        reader = CORPORA[args.corpus][0]
    if args.command == "rescore":
        return run_rescore_command(args, reader)
    report = run_census(reader, args.out, CORPORA[args.corpus][1])
    print(f"programs {report.programs}: parsed {report.parsed}, unparsable {report.unparsable}")
    print(f"families {len(report.families)}; top {TOP_ROWS} by rank (calls/selectors/forms):")
    for family in report.families[:TOP_ROWS]:
        print(
            f"  {family.family}: {family.programs} programs, {family.distinct_calls}/"
            f"{family.distinct_selectors}/{family.distinct_forms}"
        )
    print(f"digest {report.digest}")
    return 0
