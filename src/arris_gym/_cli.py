"""The `arris-gym` command line: `arris-gym census --corpus benchcad [--out DIR]` (ADR-0003).

Parses a corpus and never runs a program; the files it writes are the census
(counts, no program text) and the slice's stems.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Final

from arris_gym.census import CensusReport, CorpusProgram, benchcad, census, select_slice

Reader = Callable[[], list[CorpusProgram]]
"""Reads a corpus's programs; the CLI's seam, so a test needs no download."""

EXIT_USAGE: Final = 2
"""The exit status of a missing `[corpus]` extra, as argparse's own usage errors."""
TOP_ROWS: Final = 10
"""How many ranked families the summary prints."""
MISSING_EXTRA: Final = "arris-gym census needs the corpus extra: pip install 'arris-gym[corpus]'"


def _extra_present() -> bool:
    return all(find_spec(name) is not None for name in ("huggingface_hub", "pyarrow"))


def slice_text(report: CensusReport, stems: Sequence[str], per_family: int) -> str:
    """The `slice.txt` content: a `#` header naming the corpus and the families, then the stems."""
    corpus = report.corpus
    chosen = [f.family for f in report.families if f.programs >= per_family][
        : len(stems) // per_family
    ]
    header = [
        f"# source: {corpus.source} ({corpus.config})",
        f"# revision: {corpus.revision}",
        f"# licence: {corpus.licence}",
        f"# census digest: {report.digest}",
        f"# families: {', '.join(chosen)}",
    ]
    return "\n".join([*header, *stems, ""])


def run_census(reader: Reader, out: Path) -> CensusReport:
    """Census the programs `reader` returns, write `census.json` and `slice.txt` into `out`."""
    programs = reader()
    report = census(programs, benchcad.INFO)
    stems = select_slice(report, programs)
    out.mkdir(parents=True, exist_ok=True)
    (out / "census.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "slice.txt").write_text(slice_text(report, stems, 100), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None, *, reader: Reader | None = None) -> int:
    """Run the command; returns the exit status. `reader` replaces the corpus download (tests)."""
    parser = argparse.ArgumentParser(prog="arris-gym")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("census", help="count the API a corpus uses, never running a program")
    cmd.add_argument("--corpus", required=True, choices=["benchcad"])
    cmd.add_argument("--out", type=Path, default=Path("census-out"))
    args = parser.parse_args(argv)

    if reader is None:
        if not _extra_present():
            print(MISSING_EXTRA, file=sys.stderr)
            return EXIT_USAGE
        reader = benchcad.read
    report = run_census(reader, args.out)
    print(f"programs {report.programs}: parsed {report.parsed}, unparsable {report.unparsable}")
    print(f"families {len(report.families)}; top {TOP_ROWS} by rank (calls/selectors/forms):")
    for family in report.families[:TOP_ROWS]:
        print(
            f"  {family.family}: {family.programs} programs, {family.distinct_calls}/"
            f"{family.distinct_selectors}/{family.distinct_forms}"
        )
    print(f"digest {report.digest}")
    return 0
