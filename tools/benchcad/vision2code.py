#!/usr/bin/env python3
"""Capture Vision2Code smoke inputs and replay the frozen comparison (ADR-0032)."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from arris_gym import Sandbox, Status, dump_png, dump_text
from arris_gym.census import CorpusProgram, benchcad
from arris_gym.rescore.benchcad import SLICE, read_stems
from arris_gym.reward._scoring import DEFAULT_SCORE_TIMEOUT

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchcad._bundle import _ORACLE_LOCK, _UPSTREAM_COMMIT, _sha
from benchcad._bundle import UpstreamGrade as UpstreamGrade
from benchcad._generation import _capture_predictions
from benchcad._isolation import _job
from benchcad._qwen import _model_process
from benchcad._replay import _replay

_SOURCES = (
    "Vision2Code/pipeline/prompt.py",
    "benchcad_core/scoring/exec_cq.py",
    "benchcad_core/scoring/iou.py",
    "benchcad_core/scoring/views.py",
    "tools/_taskmods.py",
    "tools/regrade.py",
)
_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_ROWS = _ROOT / "tests/fixtures/c1/oracle.jsonl"
_SLICE_SIZE = 300
_SMOKE_TIMEOUT = 60.0
_IOU = TypeAdapter(float)
_PROMPT = TypeAdapter(tuple[str, str])

_Failure = Literal["export_error", "timeout", "crash"]


class _JobError(RuntimeError):
    def __init__(self, outcome: _Failure, message: str) -> None:
        super().__init__(message)
        self.outcome = outcome


class Upstream:
    """Run one pinned helper per isolated job. Acquire via `open_upstream(checkout)`."""

    def __init__(self, sources: Path, timeout: float) -> None:
        self._sources = sources
        self._timeout = timeout
        self._versions = json.loads(self._call("versions"))
        installed = {
            re.sub(r"[-_.]+", "-", name).lower(): version
            for name, version in self._versions["packages"].items()
        }
        locked = {
            package["name"]: package["version"]
            for package in tomllib.loads(_ORACLE_LOCK.read_text(encoding="utf-8"))["package"]
            if "virtual" not in package["source"]
        }
        if installed != locked:
            raise RuntimeError("the BenchCAD oracle venv differs from tools/oracle/uv.lock")

    def _call(self, operation: str, **inputs: bytes) -> bytes:
        result = _job(self._sources, operation, inputs, timeout=self._timeout)
        if result is None:
            raise _JobError("timeout", f"BenchCAD {operation} exceeded {self._timeout:g} s")
        status, data, stderr = result
        if status != 0 or data[:1] not in (b"E", b"K"):
            raise _JobError(
                "crash",
                f"BenchCAD {operation} exited {status}: {stderr.decode('utf-8', 'replace')}",
            )
        if data[:1] == b"E":
            outcome: _Failure = "export_error" if operation == "export" else "crash"
            raise _JobError(outcome, data[1:].decode("utf-8", "replace"))
        return data[1:]

    def extract(self, raw: str) -> bytes:
        """Return the pinned extractor's UTF-8 program for the raw response."""
        return self._call("extract", **{"raw.txt": raw.encode("utf-8")})

    def export(self, program: bytes) -> bytes:
        """Return the original STEP bytes from the pinned upstream export helper."""
        return self._call("export", **{"program.py": program})

    def render(self, target: bytes) -> bytes:
        """Render the pinned canonical four-view PNG from the supplied target STEP."""
        return self._call("render", **{"target.step": target})

    def _prompt(self, target: bytes, render: bytes) -> tuple[str, str]:
        return _PROMPT.validate_json(
            self._call("prompt", **{"target.step": target, "render.png": render})
        )

    def grade(self, target: bytes, program: bytes | None) -> UpstreamGrade:
        """Grade the given extracted program against the target, with one outcome on failure."""
        return self._grade_capture(target, program)[0]

    def _grade_capture(
        self, target: bytes, program: bytes | None
    ) -> tuple[UpstreamGrade, bytes | None]:
        if program is None:
            return UpstreamGrade(outcome="missing", iou=0), None
        if not program.decode("utf-8", "replace").strip():
            return UpstreamGrade(outcome="blank", iou=0), None
        candidate = None
        try:
            candidate = self.export(program)
            raw = self._call("score", **{"target.step": target, "candidate.step": candidate})
            iou = _IOU.validate_json(raw, strict=True)
            return UpstreamGrade(outcome="scored", iou=iou), candidate
        except _JobError as exc:
            return UpstreamGrade(
                outcome=exc.outcome,
                iou=0,
                message=str(exc),
                stage=None
                if exc.outcome == "export_error"
                else ("export" if candidate is None else "scoring"),
            ), candidate
        except ValidationError as exc:
            return UpstreamGrade(
                outcome="crash", iou=0, message=str(exc), stage="scoring"
            ), candidate

    def _regrade(
        self, target: bytes, raw: str, program: bytes | None, candidate: bytes | None
    ) -> float:
        inputs = {"target.step": target, "raw.txt": raw.encode("utf-8")}
        if program is not None:
            inputs["program.py"] = program
        if candidate is not None:
            inputs["candidate.step"] = candidate
        return _IOU.validate_json(self._call("regrade", **inputs), strict=True)


@contextmanager
def open_upstream(checkout: Path, *, timeout: float = _SMOKE_TIMEOUT) -> Iterator[Upstream]:
    """Load the scorer from the pinned commit of a local checkout and open it offline.

    For example, `with open_upstream(Path("benchcad")) as upstream:`
    followed by `upstream.extract(raw_response)`.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("the BenchCAD deadline must be positive and finite")
    with tempfile.TemporaryDirectory(prefix="benchcad-source-") as directory:
        root = Path(directory)
        for name in _SOURCES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                subprocess.check_output(
                    [
                        "/usr/bin/git",
                        "--no-replace-objects",
                        "-C",
                        str(checkout),
                        "show",
                        f"{_UPSTREAM_COMMIT}:{name}",
                    ]
                )
            )
        yield Upstream(root, timeout)


def _slice_programs(
    stems: Sequence[str], programs: list[CorpusProgram], oracle_rows: Path
) -> list[CorpusProgram]:
    if len(set(stems)) != len(stems):
        raise ValueError("duplicate stems in the C1 slice")
    selected = set(stems)
    by_stem: dict[str, CorpusProgram] = {}
    for program in programs:
        if program.stem not in selected:
            continue
        if program.stem in by_stem:
            raise ValueError(f"duplicate corpus row for {program.stem}")
        by_stem[program.stem] = program
    references: dict[str, tuple[str, str]] = {}
    for line in oracle_rows.read_bytes().splitlines():
        row = json.loads(line)
        stem = row["stem"]
        if stem in references or row["revision"] != benchcad.REVISION:
            raise ValueError(f"duplicate or unpinned C1 oracle row for {stem}")
        references[stem] = row["family"], row["report"]["program_sha256"]
    if by_stem.keys() != selected or references.keys() != selected:
        raise ValueError("the C1 slice, corpus and oracle record IDs differ")
    for stem in stems:
        program = by_stem[stem]
        if (program.family, _sha(program.text.encode("utf-8"))) != references[stem]:
            raise ValueError(f"reference family or program hash differs at {stem}")
    return [by_stem[stem] for stem in sorted(stems)]


def _smoke(checkout: Path, out: Path) -> None:
    programs = _slice_programs(read_stems(_ROOT / SLICE), benchcad.read(), _REFERENCE_ROWS)
    if len(programs) != _SLICE_SIZE:
        raise ValueError(f"the C1 slice has {len(programs)} IDs, expected {_SLICE_SIZE}")
    first: dict[str, CorpusProgram] = {}
    for reference in programs:
        first.setdefault(reference.family, reference)
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    with open_upstream(checkout) as upstream, Sandbox() as sandbox:
        for reference in first.values():
            stem = reference.stem
            target = upstream.export(reference.text.encode("utf-8"))
            imported = sandbox.read_target(target.decode("utf-8"))
            if imported.status is not Status.OK or imported.step_sha256 is None:
                raise RuntimeError(f"{stem}: {imported.status.value}: {imported.message}")
            render = upstream.render(target)
            # A syntactically complete fenced response exercises the upstream extractor.
            raw = f"```python\n{reference.text}\n```"
            program = upstream.extract(raw)
            grade, candidate = upstream._grade_capture(target, program)
            regraded = upstream._regrade(target, raw, program, candidate)
            if grade.outcome != "scored" or candidate is None or grade.iou != regraded:
                raise RuntimeError(f"{stem}: wrapper {grade}, regrader {regraded}")
            gym = sandbox.run(program.decode("utf-8"), dialect="cq")
            (out / f"{stem}.py").write_bytes(program)
            (out / f"{stem}.step").write_bytes(target)
            (out / f"{stem}.candidate.step").write_bytes(candidate)
            (out / f"{stem}.png").write_bytes(render)
            (out / f"{stem}.txt").write_text(dump_text(gym), encoding="utf-8")
            dump_png(gym, out / f"{stem}.gym.png")
            rows.append(
                {
                    "record_id": stem,
                    "family": reference.family,
                    "reference_sha256": _sha(reference.text.encode("utf-8")),
                    "extracted_sha256": _sha(program),
                    "target_sha256": _sha(target),
                    "step_sha256": imported.step_sha256,
                    "render_sha256": _sha(render),
                    "candidate_sha256": _sha(candidate),
                    "upstream_iou": grade.iou,
                    "regrader_iou": regraded,
                }
            )
        versions = upstream._versions
    evidence = {
        "code_gen_revision": benchcad.REVISION,
        "licence": benchcad.LICENCE,
        "upstream_commit": _UPSTREAM_COMMIT,
        "oracle_lock_sha256": _sha(_ORACLE_LOCK.read_bytes()),
        "versions": versions,
        "verified_ids": len(programs),
        "rows": rows,
    }
    (out / "smoke.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    smoke = commands.add_parser("smoke", help="check slice IDs and capture one target per family")
    smoke.add_argument("--upstream", type=Path, required=True)
    smoke.add_argument("--out", type=Path, required=True)
    generate = commands.add_parser("generate", help="capture one-shot predictions without scoring")
    generate.add_argument("--upstream", type=Path, required=True)
    generate.add_argument("--bundle", type=Path, required=True)
    generate.add_argument("--model-python", type=Path, required=True)
    generate.add_argument("--out", type=Path, required=True)
    generate.add_argument("--record-id", action="append", help="generate only these IDs")
    replay = commands.add_parser("replay", help="re-score a frozen bundle offline")
    replay.add_argument("--bundle", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    replay.add_argument("--record-id", help="score just this ID after validating the bundle")
    replay.add_argument("--workers", type=int)
    replay.add_argument("--score-timeout", type=float, default=DEFAULT_SCORE_TIMEOUT)
    args = parser.parse_args()
    if args.command == "smoke":
        _smoke(args.upstream, args.out)
    elif args.command == "generate":
        try:
            with (
                open_upstream(args.upstream) as upstream,
                _model_process(args.model_python) as model,
            ):
                _capture_predictions(
                    args.bundle,
                    args.out,
                    prompt=upstream._prompt,
                    generate=model,
                    extract=upstream.extract,
                    record_ids=args.record_id,
                )
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
    else:
        try:
            _replay(
                args.bundle,
                args.out,
                record_id=args.record_id,
                workers=args.workers,
                score_timeout=args.score_timeout,
            )
        except (ValueError, OSError) as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    _main()
