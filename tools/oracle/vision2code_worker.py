"""Worker for the pinned BenchCAD helpers. Start via tools/benchcad/vision2code.py."""

from __future__ import annotations

import json
import os
import shutil
import sys
from importlib.metadata import distributions
from pathlib import Path
from types import SimpleNamespace

_INPUT = Path("/inputs")
_TARGET = _INPUT / "target.step"
_CANDIDATE = _INPUT / "candidate.step"
# Precision of regrade_codegen's per-record IoU at the pinned upstream commit.
_IOU_DIGITS = 4


def _regrade(regrade, exec_cq, raw: str, code: str | None) -> float:
    """Run the pinned regrader on the exact two STEP files from separate jobs."""
    exports = iter((_TARGET, _CANDIDATE))
    extracted = []

    def extract_code(response: str) -> str:
        text = exec_cq.extract_code(response)
        extracted.append(text)
        return text

    def execute_cq_to_step(text: str, path: Path) -> None:
        source = next(exports)
        if source == _CANDIDATE and (not text.strip() or not source.is_file()):
            raise RuntimeError("no candidate STEP")
        shutil.copyfile(source, path)

    regrade._taskmods.exec_cq = lambda: SimpleNamespace(
        extract_code=extract_code, execute_cq_to_step=execute_cq_to_step
    )
    pred = [] if code is None else [{"record_id": "part", "prediction": raw}]
    row = regrade.regrade_codegen([{"record_id": "part", "gt_code": ""}], pred)
    if extracted != ([] if code is None else [code]):
        raise RuntimeError("the regrader extracted different program text")
    return row["per_record"][0]["iou"]


def _run(operation: str) -> bytes:
    sys.path.insert(0, "/upstream/tools")
    import _taskmods

    match operation:
        case "versions":
            versions = {d.metadata["Name"]: d.version for d in distributions()}
            return json.dumps({"python": sys.version.split()[0], "packages": versions}).encode()
        case "extract":
            raw = (_INPUT / "raw.txt").read_bytes().decode("utf-8")
            return _taskmods.exec_cq().extract_code(raw).encode("utf-8")
        case "export":
            code = (_INPUT / "program.py").read_bytes().decode("utf-8")
            step = Path("/tmp/export.step")
            _taskmods.exec_cq().execute_cq_to_step(code, step)
            return step.read_bytes()
        case "score":
            iou = _taskmods.iou().iou_step_vs_step(_TARGET, _CANDIDATE)
            return json.dumps(round(iou, _IOU_DIGITS)).encode()
        case "regrade":
            import regrade

            raw = (_INPUT / "raw.txt").read_bytes().decode("utf-8")
            program = _INPUT / "program.py"
            code = program.read_bytes().decode("utf-8") if program.exists() else None
            return json.dumps(_regrade(regrade, _taskmods.exec_cq(), raw, code)).encode()
        case "render":
            png = _taskmods.views().composite_for_step(_TARGET, Path("/tmp/target.png"))
            return png.read_bytes()
        case _:
            raise ValueError(f"unknown BenchCAD worker operation {operation!r}")


if __name__ == "__main__":
    # Native library diagnostics also go to stderr. Python's non-inheritable
    # duplicate carries the one frame and is closed in the program child.
    with os.fdopen(os.dup(sys.stdout.fileno()), "wb") as result:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        try:
            output = _run(sys.argv[1])
        except (OSError, RuntimeError, UnicodeError) as exc:
            result.write(b"E" + str(exc).encode("utf-8", "replace"))
        else:
            result.write(b"K" + output)
