"""Measure selected BenchCAD stems without changing their sandbox or oracle inputs."""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import platform
import subprocess
import threading
import time
from unittest.mock import patch

import arris_gym as ag
from arris_gym.fidelity import FidelityTable, TableEntry, compare, fidelity_table
from arris_gym.sandbox._zygote import JobKind, Outcome, Zygote
from cq_corpus import _read_replay, load, read_verdict_files

ROOT = pathlib.Path("tests/fixtures/c2/benchcad")


def main() -> int:
    """Write one timing and baseline comparison per stem, with no program text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stems", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--deadline", type=float, default=240.0)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args()
    wanted = sorted(set(args.stems.read_text().splitlines()))[args.shard :: args.shards]
    programs, source, licence, revision = load("benchcad")
    selected = [p for p in programs if p.stem in wanted]
    assert wanted
    assert [p.stem for p in selected] == wanted
    reports = _read_replay(ROOT / "oracle.jsonl.gz", selected, licence, revision)
    verdicts = {}
    for path in (
        "verdicts.json",
        "loft-replay/verdicts.json",
        "loft-replay/trim-verdict.json",
        "shell-replay/verdicts.json",
    ):
        for stem, raw in json.loads((ROOT / path).read_bytes()).items():
            if stem in wanted:
                assert stem not in verdicts
                verdicts[stem] = raw
    args.output.mkdir(parents=True, exist_ok=True)
    relevant = args.output / "verdicts.json"
    relevant.write_text(json.dumps(verdicts, sort_keys=True) + "\n")
    validated = read_verdict_files([relevant], wanted)
    with gzip.open(ROOT / "fidelity.json.gz", "rt", encoding="utf-8") as handle:
        expected = FidelityTable.from_json(handle.read())
    expected_entries = {entry.name: entry for entry in expected.entries if entry.name in wanted}
    print(
        f"{platform.machine()} {platform.python_version()} {platform.libc_ver()}"
        f" workers={args.workers} deadline={args.deadline} stems={len(wanted)}",
        flush=True,
    )

    stages = threading.local()
    per_sha: dict[str, dict[str, float]] = {}
    execute = Zygote.execute

    def measure(
        self: Zygote,
        kind: JobKind,
        payload: bytes,
        *,
        deadline: float,
        memory: int,
        channel: int | None = None,
    ) -> Outcome:
        start = time.monotonic()
        outcome = execute(self, kind, payload, deadline=deadline, memory=memory, channel=channel)
        stages.seconds[kind.name] = time.monotonic() - start
        return outcome

    run = ag.Sandbox._one

    def capture(
        self: ag.Sandbox,
        zygote: Zygote,
        program: str,
        dialect: ag.Dialect,
        timeout: float,
        memory: int,
    ) -> ag.ExecResult:
        stages.seconds = {}
        result = run(self, zygote, program, dialect, timeout, memory)
        per_sha[result.program_sha256] = stages.seconds
        return result

    with (
        patch.object(Zygote, "execute", measure),
        patch.object(ag.Sandbox, "_one", capture),
        ag.Sandbox() as sandbox,
    ):
        results = sandbox.run_many(
            (p.text for p in selected),
            dialect="cq",
            timeout=args.deadline,
            workers=args.workers,
        )
        assert sandbox.executions == len(selected)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with (args.output / "timings.jsonl").open("w", encoding="utf-8") as handle:
        for program, result in zip(selected, results, strict=True):
            stem = program.stem
            row = compare(result, reports[stem], validated[stem])
            actual = TableEntry(name=stem, source=source, licence=licence, row=row)
            baseline = expected_entries[stem]
            observed = {
                "stem": stem,
                "source": source,
                "licence": licence,
                "program_sha256": result.program_sha256,
                "commit": commit,
                "workers": args.workers,
                "deadline": args.deadline,
                "status": result.status.value,
                "message": result.message,
                "seconds": result.seconds,
                "phases": per_sha[result.program_sha256],
                "canonical_match": fidelity_table([actual]).digest
                == fidelity_table([baseline]).digest,
            }
            line = json.dumps(observed, sort_keys=True)
            print(line, file=handle)
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
