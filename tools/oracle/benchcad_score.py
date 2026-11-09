#!/usr/bin/env python3
"""Run BenchCAD's own scorer on our committed pair programs, and write its output.

Runs in the oracle environment (`uv run --project tools/oracle
tools/oracle/benchcad_score.py`), outside the gate and with the network: it
downloads two files of `BenchCAD/BenchCAD-main` at the commit below (MIT),
checks their SHA-256 against the pins here, and imports them from a fresh
temporary directory. Each pair under `tests/fixtures/reward/benchcad-scorer/`
holds `program.py` and `target.py` in the `cq` dialect; both run on CadQuery
here, unisolated (the programs are ours, written for this fixture, and
nothing from a corpus reaches this tool), each to a STEP file, which is what
their scorer reads. The output is `scorer.json`: for every pair, their voxel
IoU (`compute_iou`, and `iou_step_vs_step` of `benchcad_core/scoring/iou.py`
as a cross-check) and their Chamfer distance (`compute_chamfer`) repeated
`--repeats` times, since their sampling is unseeded (docs/adr/0010).

The rows are reported as the scorer returns them: a `compute_*` that fails
returns its own fallback (0.0, or infinity) with an error text, kept.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import urllib.request
from types import ModuleType
from typing import Any

import cadquery as cq
import numpy as np
import scipy
import trimesh

COMMIT = "77fd16a80a4e5fc39964ee23b6cc3225beefac8f"
RAW = f"https://raw.githubusercontent.com/BenchCAD/BenchCAD-main/{COMMIT}/"
# The two files read, and the SHA-256 of each as downloaded at COMMIT.
FILES = {
    "benchcad_core/scoring/iou.py": (
        "a53c4d4c33849a2ba2ef9dd4a8f8d3d8ca7518b2e9960d86516491e1e758c64d"
    ),
    "Vision2Code/scoring/composite_metrics.py": (
        "09f58da115fdd685b09f9195c05fe8b17f39e4681f621860242213c9985d3621"
    ),
}
PAIRS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "reward"
    / "benchcad-scorer"
)
DEFAULT_REPEATS = 100


def _shape_hash_code(self: cq.Shape) -> int:
    # The same patch as worker.py: cadquery 2.3.0 calls TopoDS_Shape.HashCode().
    return hash(self.wrapped)


cq.Shape.hashCode = _shape_hash_code  # type: ignore[method-assign]


def fetch(directory: pathlib.Path) -> dict[str, ModuleType]:
    """Download the two scorer files into `directory`, check their pins, import them."""
    modules: dict[str, ModuleType] = {}
    for name, pin in FILES.items():
        data = urllib.request.urlopen(RAW + name, timeout=60).read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != pin:
            raise SystemExit(f"{name} at {COMMIT}: sha256 {digest}, pinned {pin}")
        path = directory / pathlib.Path(name).name
        path.write_bytes(data)
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[path.stem] = module
    return modules


def step_of(program: str, path: pathlib.Path) -> None:
    """Run a trusted `cq` program on CadQuery and export its `show_object` argument to STEP."""
    shown: list[Any] = []
    exec(compile(program, "program.py", "exec"), {"show_object": shown.append})
    cq.exporters.export(shown[-1], str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=PAIRS / "scorer.json")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = parser.parse_args()
    rows: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as scratch:
        work = pathlib.Path(scratch)
        sources = work / "source"
        sources.mkdir()
        modules = fetch(sources)
        iou_module, composite = modules["iou"], modules["composite_metrics"]
        for pair in sorted(d for d in PAIRS.iterdir() if d.is_dir()):
            program, target = work / f"{pair.name}-program.step", work / f"{pair.name}-target.step"
            step_of((pair / "program.py").read_text("utf-8"), program)
            step_of((pair / "target.py").read_text("utf-8"), target)
            # gt is the target, gen the candidate, as their harness names them.
            ious = [composite.compute_iou(str(target), str(program)) for _ in range(2)]
            chamfers = [
                composite.compute_chamfer(str(target), str(program)) for _ in range(args.repeats)
            ]
            cross = iou_module.iou_step_vs_step(target, program)
            rows[pair.name] = {
                "voxel_iou_64": [v for v, _ in ious],
                "voxel_iou_64_errors": sorted({e for _, e in ious if e}),
                "voxel_iou_64_iou_py": cross,
                "chamfer": [v for v, _ in chamfers],
                "chamfer_errors": sorted({e for _, e in chamfers if e}),
            }
            print(
                pair.name,
                ious[0][0],
                min(v for v, _ in chamfers),
                max(v for v, _ in chamfers),
                file=sys.stderr,
            )
    report = {
        "scorer": "BenchCAD/BenchCAD-main",
        "commit": COMMIT,
        "files": FILES,
        "repeats": args.repeats,
        "versions": {
            "cadquery": cq.__version__,
            "trimesh": trimesh.__version__,
            "scipy": scipy.__version__,
            "numpy": np.__version__,
        },
        "pairs": rows,
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
