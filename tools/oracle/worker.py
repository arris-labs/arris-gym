"""The oracle worker: run one CadQuery program on Open CASCADE, report JSON.

Runs in the oracle environment only and imports nothing of ``arris_gym``. A
program is hostile input: it runs only as an oracle worker, this script
exec'd inside a program worker the sandbox's warden isolated (ADR-0004).

Usage, as the oracle worker: ``worker.py PAYLOAD_FD RESULT_FD`` reads the
program's text from ``PAYLOAD_FD`` to its end and writes one JSON report to
``RESULT_FD``, only from the process that started (a child the program
forked writes nothing). For a trusted program by hand, ``worker.py
PROGRAM.py`` prints the report on stdout.

The result is taken as ``docs/ARCHITECTURE.md`` §Outcomes says: the argument
of the last ``show_object`` call, else the module-level ``result``.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import traceback
from typing import Any

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Interface import Interface_Static
from OCP.OSD import OSD_ThreadPool
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

_FILENAME = "program.py"


def _shape_hash_code(self: cq.Shape) -> int:
    # cadquery 2.3.0 calls TopoDS_Shape.HashCode(), which OCP 7.9 removed; it
    # keys every selector (`faces`, `edges`, ...) on it. TopoDS_Shape's own
    # hash agrees with IsSame, the identity cadquery means. Nothing else of
    # cadquery is patched.
    return hash(self.wrapped)


cq.Shape.hashCode = _shape_hash_code  # type: ignore[method-assign]
# Open CASCADE's default thread pool has a thread per logical processor, and
# cadquery runs every boolean in parallel on it. Under the worker's
# RLIMIT_NPROC the pool cannot start them and the boolean hangs (ADR-0004),
# and its size would make a report depend on the machine. The pool is created
# here, before any program, with one thread: the calling one.
OSD_ThreadPool.DefaultPool_s(1)
# STEP's header carries a timestamp, and the product name a per-process counter
# ("translator 7.9 2"); the data section is hashed with the counter blanked.
_STEP_DATA_MARK = b"DATA;"
_STEP_COUNTER = re.compile(rb"(translator \d+\.\d+ )\d+")


def _count(shape: cq.Shape, kind: Any) -> int:
    n = 0
    explorer = TopExp_Explorer(shape.wrapped, kind)
    while explorer.More():
        n += 1
        explorer.Next()
    return n


def _as_shape(result: Any) -> cq.Shape | None:
    """The shape a result stands for, or None when it is not geometry."""
    if isinstance(result, cq.Workplane):
        shapes = [v for v in result.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            return None
        return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(result, cq.Shape):
        return result
    return None


def _measures(shape: cq.Shape) -> dict[str, Any]:
    vol = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, vol)
    surf = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape.wrapped, surf)
    c = vol.CentreOfMass()
    box = Bnd_Box()
    BRepBndLib.Add_s(shape.wrapped, box)
    lo_x, lo_y, lo_z, hi_x, hi_y, hi_z = box.Get()
    return {
        "volume": vol.Mass(),
        "area": surf.Mass(),
        "centroid": [c.X(), c.Y(), c.Z()],
        "bounds": [[lo_x, lo_y, lo_z], [hi_x, hi_y, hi_z]],
        "faces": _count(shape, TopAbs_FACE),
        "solids": _count(shape, TopAbs_SOLID),
    }


def _step_sha256(shape: cq.Shape) -> str:
    # As ``cq.exporters.export`` writes STEP (a compound, ``Shape.exportStep``'s
    # defaults), but to memory: an oracle worker can write no file.
    writer = STEPControl_Writer()
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 1)
    Interface_Static.SetIVal_s("write.precision.mode", 0)
    writer.Transfer(cq.Compound.makeCompound([shape]).wrapped, STEPControl_AsIs)
    stream = io.BytesIO()
    writer.WriteStream(stream)
    data = stream.getvalue()
    return hashlib.sha256(
        _STEP_COUNTER.sub(rb"\1N", data[data.index(_STEP_DATA_MARK) :])
    ).hexdigest()


def run_program(text: str) -> dict[str, Any]:
    """Run ``text`` and return its report: status, message, measures, hashes.

    Statuses: ``ok``, ``syntax``, ``runtime``, ``no_result`` and ``invalid``
    (``BRepCheck_Analyzer`` fails). Messages are the exception's own words.
    """
    report: dict[str, Any] = {
        "status": "ok",
        "message": "",
        "measures": None,
        "step_sha256": None,
        "program_sha256": hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest(),
        "versions": {
            "cadquery": cq.__version__,
            "ocp": _ocp_version(),
            "python": sys.version.split()[0],
        },
    }
    try:
        code = compile(text, _FILENAME, "exec")
    except (SyntaxError, ValueError) as exc:  # ValueError: a NUL byte
        report.update(status="syntax", message=f"{type(exc).__name__}: {exc}")
        return report

    shown: list[Any] = []
    ns: dict[str, Any] = {"__name__": "__main__", "show_object": shown.append}
    try:
        exec(code, ns)
    except BaseException as exc:  # noqa: BLE001 - SystemExit included: the program's own end
        tb = traceback.format_exception_only(type(exc), exc)
        report.update(status="runtime", message="".join(tb).rstrip("\n"))
        return report

    result = shown[-1] if shown else ns.get("result")
    shape = _as_shape(result) if result is not None else None
    if shape is None:
        what = "nothing" if result is None else type(result).__name__
        report.update(status="no_result", message=f"no shape result: {what}")
        return report
    report["measures"] = _measures(shape)
    if not BRepCheck_Analyzer(shape.wrapped).IsValid():
        report.update(status="invalid", message="BRepCheck_Analyzer: shape is not valid")
        return report
    report["step_sha256"] = _step_sha256(shape)
    return report


def _ocp_version() -> str:
    from importlib.metadata import version

    return version("cadquery-ocp")


def _read_all(fd: int) -> bytes:
    chunks = []
    while chunk := os.read(fd, 1 << 20):
        chunks.append(chunk)
    os.close(fd)
    return b"".join(chunks)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def main() -> None:
    worker = os.getpid()
    if len(sys.argv) == 3:  # the oracle worker: payload and result descriptors
        text = _read_all(int(sys.argv[1])).decode("utf-8", "surrogatepass")
        out = int(sys.argv[2])
    else:
        with open(sys.argv[1], encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        # Open CASCADE's STEP writer prints to C stdout; keep fd 1 for the JSON.
        out = os.dup(1)
        os.dup2(2, 1)
    report = json.dumps(run_program(text), sort_keys=True) + "\n"
    # A child the program forked returns here too; only the worker reports.
    if os.getpid() == worker:
        _write_all(out, report.encode("utf-8", "surrogatepass"))


if __name__ == "__main__":
    main()
