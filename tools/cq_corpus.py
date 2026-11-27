#!/usr/bin/env python3
"""Compare corpus programs run under `cq` with live or pinned oracle reports.

Generalises `cq_slice.py` and `oracle_run.py` to `--corpus benchcad|cadrecode`
(the `[corpus]` extra, the Hugging Face cache or the network, and
`uv sync --project tools/oracle` for live oracle runs; outside the gate).
Every selected program runs in the sandbox under `dialect="cq"`. The tool
compares each result with its oracle report. Written under `--out-dir` (default
`tests/fixtures/c2/<corpus>/`), gzipped with `mtime=0`:

- `fidelity.json.gz`: the `FidelityTable` (names, SHA-256s, measures, licence);
- `oracle.jsonl.gz`: the oracle's rows without STEP text or wall-clock time;
- `arris-report.json` / `.md`: what arris's maintainers act on (ADR-0006);
- `reach-report.json`: the `ReachReport` under today's `cq.subset()` (ADR-0012).

No program text is written. Work is saved in chunks under `--work-dir` and a
run with `--budget` stops between chunks (exit 3); run it again to resume.
`--verdicts FILE...` classes rows by stem (C1's and a corpus's own).
`--slice FILE` restricts either corpus to a slice's stems. `--oracle-rows FILE` (a
committed `oracle.jsonl.gz`) reuses each row whose program SHA-256 matches and
whose versions are those of the oracle this run probes, and runs the oracle only
on the rest: a change to `cq` alone re-runs `cq` alone. The oracle's bytes vary
from run to run (BACKLOG `oracle-nondeterministic-step`), so a re-run would only
draw them again.

`--replay-oracle-rows FILE` compares against the pinned reports with no live
oracle. It requires one answered report per selected stem, from the same
program SHA-256, family, licence and revision. A replay with `--slice`
accepts the full corpus's verdict files and applies verdicts to selected stems.
"""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any

import arris_gym as ag
import cq_slice
import oracle_run
from arris_gym.census import CorpusProgram, census_program
from arris_gym.cq import subset
from arris_gym.fidelity import (
    OracleReport,
    OracleVersions,
    TableEntry,
    Verdict,
    arris_rows,
    compare,
    fidelity_table,
    program_sha256,
    reach_report,
)

C2 = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "c2"
# The sandbox's own deadline for a program, as `cq_slice.py` has it.
TIMEOUT = 30.0
# The oracle's deadline for a corpus run, the `--oracle-timeout` default (ADR-0013's 2026-11-21
# amendment): the next multiple of 30 s above 4 x the slowest program measured on BenchCAD
# (57.3 s, a `double_simplex_sprocket`, under 16 workers), so load does not move a status.
# It stays below `oracle_run.ZYGOTE_LIFETIME` less the sandbox's `BACKSTOP`.
ORACLE_TIMEOUT = 240.0
# Programs per saved chunk: a chunk's sandbox and oracle runs finish in one foreground call
# (under ~110 s at the baseline's rates), and an interrupted run loses at most one chunk.
CHUNK = 500
# Exit status of a run that spent its `--budget`: run it again to resume.
RESUME = 3
# The program `oracle_versions` runs to learn which oracle this run uses.
PROBE = 'import cadquery as cq\n\nresult = cq.Workplane("XY").box(1, 1, 1)\n'


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


def read_oracle(path: pathlib.Path) -> dict[str, OracleReport]:
    """The reports of an `oracle.jsonl.gz` this tool wrote, by program SHA-256."""
    reports = {}
    for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
        report = OracleReport.model_validate(json.loads(line)["report"])
        reports[report.program_sha256] = report
    return reports


def _read_replay(
    path: pathlib.Path, programs: Sequence[CorpusProgram], licence: str, revision: str
) -> dict[str, OracleReport]:
    selected = {p.stem: p for p in programs}
    reports: dict[str, OracleReport] = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            stem = row["stem"]
            if stem not in selected:
                continue
            if stem in reports:
                raise ValueError(f"{stem}: duplicate replay report")
            program = selected[stem]
            for field, expected in (
                ("family", program.family),
                ("licence", licence),
                ("revision", revision),
            ):
                if row.get(field) != expected:
                    raise ValueError(f"{stem}: replay {field} does not match the corpus")
            report = OracleReport.model_validate(row["report"])
            if report.program_sha256 != program_sha256(program.text):
                raise ValueError(f"{stem}: replay program SHA-256 does not match the corpus")
            if report.versions is None:
                raise ValueError(f"{stem}: unanswered replay report ({report.status.value})")
            reports[stem] = report
    missing = sorted(selected.keys() - reports.keys())
    if missing:
        raise ValueError(f"{len(missing)} missing replay reports, starting with {missing[0]}")
    return reports


def reusable(
    saved: Mapping[str, OracleReport], versions: OracleVersions
) -> dict[str, OracleReport]:
    """The saved reports the oracle of `versions` gave. A timeout or a crash carries no
    versions, so it is never reused: a timeout is never cached."""
    return {sha: r for sha, r in saved.items() if r.versions == versions}


def oracle_versions(args: argparse.Namespace) -> OracleVersions:
    """The versions of the oracle this run uses, read from its report of `PROBE`."""
    (report,) = oracle_run.run_many([PROBE], timeout=args.oracle_timeout, workers=1)
    if report.versions is None:
        raise ValueError(f"the oracle did not answer the probe: {report.status.value}")
    return report.versions


def read_verdict_files(paths: Sequence[pathlib.Path], stems: Sequence[str]) -> dict[str, Verdict]:
    """The verdicts of several `verdicts.json` files by stem.

    Raises `ValueError` for a stem two files both class: one row has one verdict.
    """
    verdicts: dict[str, Verdict] = {}
    for path in paths:
        for stem, verdict in cq_slice.read_verdicts(path, stems).items():
            if stem in verdicts:
                raise ValueError(f"{stem} has a verdict in two files")
            verdicts[stem] = verdict
    return verdicts


def merge_reports(
    texts: Sequence[str],
    shas: Sequence[str],
    known: Mapping[str, OracleReport],
    run: Callable[[Sequence[str]], list[OracleReport]],
) -> list[OracleReport]:
    """One report per program, in order: `known`'s for its SHA-256, else `run`'s.

    `run` gets only the programs `known` lacks, and is not called when it lacks none.
    """
    missing = [text for text, sha in zip(texts, shas, strict=True) if sha not in known]
    fresh = iter(run(missing) if missing else [])
    return [known[sha] if sha in known else next(fresh) for sha in shas]


def run_programs(
    part: Sequence[CorpusProgram],
    args: argparse.Namespace,
    pin: tuple[str, str, str],
    verdicts: dict[str, Verdict],
    known: Mapping[str, OracleReport],
    replay: Mapping[str, OracleReport] | None = None,
) -> dict[str, Any]:
    """Run `part` under cq and return the entries and oracle rows for a chunk.

    Use pinned `replay` reports by stem when provided. Otherwise use `known`
    reports by SHA-256 and run the oracle for the missing programs.
    """
    source, licence, revision = pin
    texts = [p.text for p in part]
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(texts, dialect="cq", timeout=args.timeout, workers=args.workers)
    if replay is None:
        reports = merge_reports(
            texts,
            [r.program_sha256 for r in results],
            known,
            lambda ts: oracle_run.run_many(ts, timeout=args.oracle_timeout, workers=args.workers),
        )
    else:
        reports = [replay[p.stem] for p in part]
    entries = []
    for program, result, report in zip(part, results, reports, strict=True):
        if result.program_sha256 != report.program_sha256:
            raise ValueError(f"{program.stem}: the oracle ran another program")
        row = compare(result, report, verdicts.get(program.stem))
        entries.append(TableEntry(name=program.stem, source=source, licence=licence, row=row))
    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "oracle": rows(part, reports, licence, revision),
    }


def retry_timeouts(
    part: Sequence[CorpusProgram],
    data: dict[str, Any],
    rerun: Callable[[Sequence[CorpusProgram]], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """`data` (a saved chunk's body) with each timed-out program's entry and oracle row rerun.

    A timeout is the one outcome a slower machine changes, so it is never cached: every
    other saved row is kept as it is. Returns the body and whether any program was rerun.
    """
    again = [i for i, e in enumerate(data["entries"]) if TableEntry.model_validate(e).row.timed_out]
    if not again:
        return data, False
    fresh = rerun([part[i] for i in again])
    entries = list(data["entries"])
    oracle = list(data["oracle"])
    for i, entry, row in zip(again, fresh["entries"], fresh["oracle"], strict=True):
        entries[i], oracle[i] = entry, row
    return {"entries": entries, "oracle": oracle}, True


def main(argv: Sequence[str] | None = None) -> int:
    """Run the corpus and write the rows; print the counts and digests to stderr."""
    parser = argparse.ArgumentParser(
        description="Compare corpus programs run under cq with live or pinned oracle reports."
    )
    parser.add_argument("--corpus", choices=("benchcad", "cadrecode"), required=True)
    parser.add_argument("--slice", type=pathlib.Path, help="corpus stems to run, one per line")
    parser.add_argument(
        "--verdicts",
        type=pathlib.Path,
        nargs="+",
        default=[],
        help="stem -> Verdict files, as cq_slice.py; a stem in two files is an error",
    )
    parser.add_argument("--out-dir", type=pathlib.Path)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--oracle-timeout", type=float, default=ORACLE_TIMEOUT)
    parser.add_argument("--chunk", type=int, default=CHUNK, help="programs per saved chunk")
    parser.add_argument("--budget", type=float, help="stop starting chunks after this many seconds")
    parser.add_argument("--work-dir", type=pathlib.Path, help="saved chunks; default OUT/.work")
    parser.add_argument("--workers", type=int, default=oracle_run.DEFAULT_WORKERS)
    oracle_input = parser.add_mutually_exclusive_group()
    oracle_input.add_argument(
        "--oracle-rows", type=pathlib.Path, help="a committed oracle.jsonl.gz whose rows to reuse"
    )
    oracle_input.add_argument(
        "--replay-oracle-rows",
        type=pathlib.Path,
        help="require pinned reports from oracle.jsonl.gz for every selected stem",
    )
    args = parser.parse_args(argv)

    corpus_programs, source, licence, revision = load(args.corpus)
    programs = corpus_programs
    if args.slice is not None:
        wanted = set(oracle_run.read_slice(args.slice))
        programs = [p for p in programs if p.stem in wanted]
        if len(programs) != len(wanted):
            raise ValueError("stems the corpus lacks")
    out_dir = args.out_dir or C2 / args.corpus
    verdict_programs = corpus_programs if args.replay_oracle_rows is not None else programs
    verdicts = read_verdict_files(args.verdicts, [p.stem for p in verdict_programs])
    known: dict[str, OracleReport] = {}
    replay = None
    if args.oracle_rows is not None:
        known = reusable(read_oracle(args.oracle_rows), oracle_versions(args))
        print(f"reusing {len(known)} oracle rows of {args.oracle_rows}", file=sys.stderr)
    elif args.replay_oracle_rows is not None:
        replay = _read_replay(args.replay_oracle_rows, programs, licence, revision)
        print(f"replaying {len(replay)} oracle rows of {args.replay_oracle_rows}", file=sys.stderr)
    run_part = partial(
        run_programs,
        args=args,
        pin=(source, licence, revision),
        verdicts=verdicts,
        known=known,
        replay=replay,
    )
    work = args.work_dir or out_dir / ".work"
    work.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    entries: list[TableEntry] = []
    oracle_rows: list[dict[str, object]] = []
    start = 0
    while start < len(programs):
        # A saved chunk of any size at `start` is read as it is; a new one has `--chunk` programs.
        # Two files for one start are a work dir from different `--chunk` sizes: fail, never pick.
        found = sorted(work.glob(f"chunk-{start:06d}-*.json.gz"))
        if len(found) > 1:
            raise ValueError(f"{[f.name for f in found]} share a start: remove the work dir")
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
            chunk.write_bytes(gz(json.dumps(run_part(part), sort_keys=True)))
        data = json.loads(gzip.decompress(chunk.read_bytes()))
        if replay is not None and data["oracle"] != rows(
            part, [replay[p.stem] for p in part], licence, revision
        ):
            raise ValueError(f"{chunk} does not match the pinned oracle rows: remove the work dir")
        data, rerun = retry_timeouts(part, data, run_part)
        if rerun:
            chunk.write_bytes(gz(json.dumps(data, sort_keys=True)))
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
