#!/usr/bin/env python3
"""Run programs on the oracle: CadQuery on Open CASCADE in an oracle worker.

An oracle worker is a program worker under the sandbox's warden that execs
the oracle environment's interpreter on `tools/oracle/worker.py` (ADR-0004):
the same namespaces, rlimits, Landlock domain and seccomp filter as an arris
program, with the oracle environment's prefixes as its whole reach. Runs in
the main environment; needs `uv sync --project tools/oracle` first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from arris_gym.fidelity import OracleReport, parse_outcome
from arris_gym.sandbox import _exec
from arris_gym.sandbox._zygote import ENVIRONMENT, JobKind, Outcome, Zygote

ORACLE = pathlib.Path(__file__).resolve().parent / "oracle"
# The environment's interpreter as it is called: the path tells it its venv.
PYTHON = ORACLE / ".venv" / "bin" / "python"
WORKER = ORACLE / "worker.py"

# The oracle worker's RLIMIT_AS. Measured (ADR-0004): importing cadquery and
# OCP maps 875 MiB of address space, and a filleted box with a hole and five
# booleans on spheres and cylinders left it there; its resident set was
# 507 MiB. 1.5 GiB is that import plus about what an arris worker's 512 MiB
# leaves a program beyond its own import, and refuses a 1 GiB allocation.
MEMORY = 1536 * 2**20

# The zygote's environment, and a `HOME` that does not exist: ezdxf, which
# cadquery imports, asks the password database for one without it, and the
# worker cannot read that. Nothing is written there; the read-only mounts
# refuse it.
ORACLE_ENVIRONMENT = {**ENVIRONMENT, "HOME": "/nonexistent"}


def spec() -> _exec.ExecSpec:
    """The exec spec of an oracle worker on this checkout's oracle environment."""
    return _exec.interpreter_spec(str(PYTHON), str(WORKER), ORACLE_ENVIRONMENT)


def run_one(zygote: Zygote, oracle: _exec.ExecSpec, program: str, *, timeout: float) -> Outcome:
    """Run `program` in one oracle worker for at most `timeout` seconds.

    What came back, unread: the warden's `Ending`, the frame bytes on the
    result pipe (trusted no more than any worker's) and the stderr tail.
    """
    text = program.encode("utf-8", "surrogatepass")
    return zygote.execute(
        JobKind.EXEC,
        _exec.payload(oracle, text),
        deadline=time.monotonic() + timeout,
        memory=MEMORY,
    )


# The oracle worker's deadline when none is given. Its start-up is about
# 1.5 s of the import (ADR-0004), so this leaves a program 28 s of its own.
DEFAULT_TIMEOUT = 30.0
# Oracle workers run at once. Each is 1.5 GiB of address space at most and
# one thread; the report does not depend on the number.
DEFAULT_WORKERS = 4


def run_report(
    zygote: Zygote, oracle: _exec.ExecSpec, program: str, *, timeout: float
) -> OracleReport:
    """The `OracleReport` of `program`: one oracle worker, its frame parsed.

    Never raises on a program; a frame that cannot be believed is a `crash`.
    """
    start = time.monotonic()
    outcome = run_one(zygote, oracle, program, timeout=timeout)
    return parse_outcome(outcome, program, timeout=timeout, seconds=time.monotonic() - start)


def run_many(
    programs: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT, workers: int = DEFAULT_WORKERS
) -> list[OracleReport]:
    """The reports of `programs`, in submission order whatever order they finish."""
    oracle = spec()
    with Zygote() as zygote, ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda p: run_report(zygote, oracle, p, timeout=timeout), programs))


def read_slice(path: pathlib.Path) -> list[str]:
    """The stems of a slice file: one per line, `#` lines are its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def slice_rows(
    stems: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT, workers: int = DEFAULT_WORKERS
) -> list[dict[str, object]]:
    """The oracle rows of BenchCAD programs by stem, sorted by stem.

    Reads the pinned corpus through `census.benchcad` (the `[corpus]` extra
    and the network, outside the gate). Each row is the stem, family, licence
    and revision beside the report without its STEP text and wall-clock
    `seconds`, so the rows are the same bytes on every run. Raises `ValueError` for a stem the
    corpus lacks or lists twice.
    """
    from arris_gym.census import benchcad

    by_stem = {p.stem: p for p in benchcad.read()}
    ordered = sorted(stems)
    if len(set(ordered)) != len(ordered):
        raise ValueError("a stem is listed twice")
    missing = [stem for stem in ordered if stem not in by_stem]
    if missing:
        raise ValueError(f"stems not in the pinned corpus: {missing[:5]}")
    programs = [by_stem[stem] for stem in ordered]
    reports = run_many([p.text for p in programs], timeout=timeout, workers=workers)
    return [
        {
            "stem": p.stem,
            "family": p.family,
            "licence": benchcad.LICENCE,
            "revision": benchcad.REVISION,
            "report": json.loads(r.model_dump_json(exclude={"step", "seconds"})),
        }
        for p, r in zip(programs, reports, strict=True)
    ]


def rows_text(rows: Sequence[dict[str, object]]) -> str:
    """The rows as `oracle.jsonl` text: one canonical JSON object per line."""
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def rows_digest(text: str) -> str:
    """The digest of an `oracle.jsonl`: the SHA-256 of its text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the given program files and write `oracle.jsonl`: one row per program
    in the order given, `{"path": ..., "report": ...}`, `seconds` included and
    the STEP text left out.
    With `--slice FILE`, run the BenchCAD programs of those stems instead
    (`slice_rows`), sorted by stem, and print the status counts and digest."""
    parser = argparse.ArgumentParser(description="Run programs on the oracle.")
    parser.add_argument("programs", nargs="*", type=pathlib.Path)
    parser.add_argument("--slice", type=pathlib.Path, help="a slice file of BenchCAD stems")
    parser.add_argument("--start", type=int, default=0, help="with --slice: first stem to run")
    parser.add_argument("--stop", type=int, help="with --slice: stop before this stem")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("oracle.jsonl"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args(argv)
    if (args.slice is None) == (not args.programs):
        parser.error("give program files, or --slice FILE, not both and not neither")
    if args.slice is not None:
        stems = sorted(read_slice(args.slice))[args.start : args.stop]
        rows = slice_rows(stems, timeout=args.timeout, workers=args.workers)
        text = rows_text(rows)
        args.out.write_text(text, encoding="utf-8")
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row["report"]["status"])  # type: ignore[index]
            counts[status] = counts.get(status, 0) + 1
        print(f"{len(rows)} programs: {dict(sorted(counts.items()))}", file=sys.stderr)
        print(f"digest {rows_digest(text)}", file=sys.stderr)
        return 0
    texts = [p.read_text(encoding="utf-8", errors="surrogateescape") for p in args.programs]
    reports = run_many(texts, timeout=args.timeout, workers=args.workers)
    with args.out.open("w", encoding="utf-8") as out:
        for path, report in zip(args.programs, reports, strict=True):
            row = {
                "path": str(path),
                "report": json.loads(report.model_dump_json(exclude={"step"})),
            }
            out.write(json.dumps(row, sort_keys=True) + "\n")
    counts = {}
    for report in reports:
        counts[report.status.value] = counts.get(report.status.value, 0) + 1
    print(f"{len(reports)} programs: {dict(sorted(counts.items()))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
