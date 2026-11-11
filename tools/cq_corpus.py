#!/usr/bin/env python3
"""Run a whole corpus under `cq` and on the oracle; write its fidelity rows and reach report.

Generalises `cq_slice.py` and `oracle_run.py` to `--corpus benchcad|cadrecode`
(the `[corpus]` extra, the Hugging Face cache or the network, and
`uv sync --project tools/oracle`; outside the gate). Every corpus program runs in
the sandbox under `dialect="cq"` and on an oracle zygote (ADR-0013); each pair
is compared (`fidelity.compare`, no verdicts: a row the rule cannot class is
counted unclassified, never worked here). Written under `--out-dir` (default
`tests/fixtures/c2/<corpus>/`), gzipped with `mtime=0`:

- `fidelity.json.gz`: the `FidelityTable` (names, SHA-256s, measures, licence);
- `oracle.jsonl.gz`: the oracle's rows without STEP text or wall-clock time;
- `arris-report.json` / `.md`: what arris's maintainers act on (ADR-0006);
- `reach-report.json`: the `ReachReport` under the C1 subset (ADR-0012).

No program text is written. Work is saved in chunks under `--work-dir` and a
run with `--budget` stops between chunks (exit 3); run it again to resume.
`--slice FILE` restricts BenchCAD to a slice's stems.
"""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import time
from collections.abc import Sequence

import arris_gym as ag
import cq_slice
import oracle_run
from arris_gym.census import CorpusProgram, census_program
from arris_gym.cq import subset
from arris_gym.fidelity import (
    OracleReport,
    TableEntry,
    Verdict,
    arris_rows,
    compare,
    fidelity_table,
    reach_report,
)

C2 = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "c2"
# The sandbox's own deadline for a program, as `cq_slice.py` has it.
TIMEOUT = 30.0
CHUNK = 500
# Exit status of a run that spent its `--budget`: run it again to resume.
RESUME = 3


def load(corpus: str) -> tuple[list[CorpusProgram], str, str, str]:
    """The pinned corpus's programs sorted by stem, its source string, licence and revision."""
    if corpus == "benchcad":
        from arris_gym.census import benchcad

        programs = benchcad.read()
        pin = (benchcad.REPO, benchcad.REVISION, benchcad.CONFIG, benchcad.LICENCE)
    elif corpus == "cadrecode":
        from arris_gym.census import cadrecode

        programs = cadrecode.read()
        pin = (cadrecode.REPO, cadrecode.REVISION, cadrecode.CONFIG, cadrecode.LICENCE)
    else:
        raise ValueError(f"unknown corpus {corpus!r}")
    repo, revision, config, licence = pin
    return sorted(programs, key=lambda p: p.stem), f"{repo}@{revision}/{config}", licence, revision


def gz(text: str) -> bytes:
    """`text` gzipped with `mtime=0`, so equal text is equal bytes."""
    return gzip.compress(text.encode("utf-8"), mtime=0)


def rows(
    programs: Sequence[CorpusProgram],
    reports: Sequence[OracleReport],
    licence: str,
    revision: str,
) -> list[dict[str, object]]:
    """The oracle rows, as `oracle_run.slice_rows` has them: the licence and revision of the
    corpus beside each report without its STEP text and wall-clock `seconds`."""
    return [
        {
            "stem": p.stem,
            "family": p.family,
            "licence": licence,
            "revision": revision,
            "report": json.loads(r.model_dump_json(exclude={"step", "seconds"})),
        }
        for p, r in zip(programs, reports, strict=True)
    ]


def run_chunk(
    part: Sequence[CorpusProgram],
    path: pathlib.Path,
    args: argparse.Namespace,
    pin: tuple[str, str, str],
    verdicts: dict[str, Verdict],
) -> None:
    """Run `part` under cq and on the oracle and save its entries and oracle rows at `path`.

    A saved chunk is never rerun, so a corpus run is resumable and its pieces each fit a
    short foreground call; the rows are the same bytes either way.
    """
    source, licence, revision = pin
    texts = [p.text for p in part]
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(texts, dialect="cq", timeout=args.timeout, workers=args.workers)
    reports = oracle_run.run_many(texts, timeout=args.oracle_timeout, workers=args.workers)
    entries = []
    for program, result, report in zip(part, results, reports, strict=True):
        if result.program_sha256 != report.program_sha256:
            raise ValueError(f"{program.stem}: the oracle ran another program")
        row = compare(result, report, verdicts.get(program.stem))
        entries.append(TableEntry(name=program.stem, source=source, licence=licence, row=row))
    body = {
        "entries": [e.model_dump(mode="json") for e in entries],
        "oracle": rows(part, reports, licence, revision),
    }
    path.write_bytes(gz(json.dumps(body, sort_keys=True)))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the corpus and write the rows; print the counts and digests to stderr."""
    parser = argparse.ArgumentParser(description="Run a whole corpus under cq and on the oracle.")
    parser.add_argument("--corpus", choices=("benchcad", "cadrecode"), required=True)
    parser.add_argument("--slice", type=pathlib.Path, help="BenchCAD stems to run, one per line")
    parser.add_argument("--verdicts", type=pathlib.Path, help="stem -> Verdict, as cq_slice.py")
    parser.add_argument("--out-dir", type=pathlib.Path)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--oracle-timeout", type=float, default=oracle_run.DEFAULT_TIMEOUT)
    parser.add_argument("--chunk", type=int, default=CHUNK, help="programs per saved chunk")
    parser.add_argument("--budget", type=float, help="stop starting chunks after this many seconds")
    parser.add_argument("--work-dir", type=pathlib.Path, help="saved chunks; default OUT/.work")
    parser.add_argument("--workers", type=int, default=oracle_run.DEFAULT_WORKERS)
    args = parser.parse_args(argv)

    programs, source, licence, revision = load(args.corpus)
    if args.slice is not None:
        wanted = set(oracle_run.read_slice(args.slice))
        programs = [p for p in programs if p.stem in wanted]
        if len(programs) != len(wanted):
            raise ValueError("stems the corpus lacks")
    out_dir = args.out_dir or C2 / args.corpus
    verdicts = (
        cq_slice.read_verdicts(args.verdicts, [p.stem for p in programs]) if args.verdicts else {}
    )
    work = args.work_dir or out_dir / ".work"
    work.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    entries: list[TableEntry] = []
    oracle_rows: list[dict[str, object]] = []
    start = 0
    while start < len(programs):
        # A saved chunk of any size at `start` is read as it is; a new one has `--chunk` programs.
        found = sorted(work.glob(f"chunk-{start:06d}-*.json.gz"))
        if found:
            chunk = found[0]
            size = int(chunk.name.split("-")[2].split(".")[0])
        else:
            size = args.chunk
            chunk = work / f"chunk-{start:06d}-{size}.json.gz"
        part = programs[start : start + size]
        if not chunk.is_file():
            if args.budget is not None and time.monotonic() - started > args.budget:
                done = len(list(work.glob("chunk-*.json.gz")))
                print(f"budget spent: {done} chunks done; run again to resume", file=sys.stderr)
                return RESUME
            run_chunk(part, chunk, args, (source, licence, revision), verdicts)
        data = json.loads(gzip.decompress(chunk.read_bytes()))
        saved = [TableEntry.model_validate(e) for e in data["entries"]]
        if [e.name for e in saved] != [p.stem for p in part]:
            raise ValueError(f"{chunk} is not the chunk of these programs: remove the work dir")
        entries.extend(saved)
        oracle_rows.extend(data["oracle"])
        start += len(part)
    table = fidelity_table(entries)
    reach = reach_report(table, [census_program(p) for p in programs], subset())
    arris = arris_rows(table)
    oracle_text = oracle_run.rows_text(oracle_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fidelity.json.gz").write_bytes(gz(table.to_json() + "\n"))
    (out_dir / "oracle.jsonl.gz").write_bytes(gz(oracle_text))
    (out_dir / "arris-report.json").write_text(arris.to_json() + "\n", encoding="utf-8")
    (out_dir / "arris-report.md").write_text(arris.to_markdown(), encoding="utf-8")
    (out_dir / "reach-report.json").write_text(reach.to_json() + "\n", encoding="utf-8")
    print(f"{table.programs} programs", file=sys.stderr)
    for key in ("outcomes", "classes", "statuses", "oracle_statuses"):
        print(f"{key}: {getattr(table, key)}", file=sys.stderr)
    print(f"timed out: {list(table.timed_out)}", file=sys.stderr)
    print(f"reach: {reach.in_subset}/{reach.programs}", file=sys.stderr)
    print(
        f"in-subset cq_bug {reach.in_subset_cq_bug}, by_design {reach.in_subset_by_design}",
        file=sys.stderr,
    )
    print(f"table digest {table.digest}", file=sys.stderr)
    print(f"oracle digest {oracle_run.rows_digest(oracle_text)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
