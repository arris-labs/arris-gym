#!/usr/bin/env python3
"""What CadQuery's `faces(sel).workplane()` selects and places, read on the oracle (ADR-0017).

The evidence of ADR-0017. Each probed program runs on an oracle zygote (ADR-0013)
with a prelude that wraps CadQuery's `Workplane.faces` and `Workplane.workplane`:
the first `workplane()` called on a stack that `faces(…)` made records what was
selected and the plane it builds, then stops the program by raising `ProbeRecord`
with the record as its JSON message. The worker reports it as a `runtime` status
whose message is the exception's own words (`tools/oracle/worker.py`), so nothing
of the oracle changes. A program that ends before such a call keeps its own
status and message.

Two sets are probed:

- `--corpus`: the BenchCAD programs (the `[corpus]` extra and its Hugging Face
  cache or the network) admitted by adding `faces(str)`, `hole(num)` and the
  six axis selectors to the subset before that bundle (ADR-0017).
  `--range START:STOP` probes a slice of them, sorted by stem, into
  `--work-dir/part-START.json`, so each run fits one foreground call;
- `--constructed`: the named constructions in `CONSTRUCTED`, own programs whose
  answer has a closed form.

`--merge` joins the parts and the constructions into `--out-dir`: `benchcad.jsonl.gz`
(one row per program: stem, family, licence, revision, program SHA-256, status,
message unless a record, the record), `constructed.json` (the programs and their
records) and `counts.json` (the corpus rows counted by family and outcome). No
corpus program text is written. Outside the gate: the oracle environment is needed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import oracle_run
from arris_gym.census import CorpusProgram, ProgramCensus, Unparsable, census_program, reach
from arris_gym.cq import CensusForm, Subset, subset
from arris_gym.fidelity import OracleReport, OracleStatus

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "selectors"
TIMEOUT = 30.0
WORKERS = 8
SELECTORS = (">X", "<X", ">Y", "<Y", ">Z", "<Z")
BUNDLE = (
    CensusForm("Workplane.faces", (("str",),)),
    CensusForm("Workplane.hole", (("num",),)),
)
# The prefix of a record in the worker's runtime message (`format_exception_only`).
MARK = "ProbeRecord: "

# Run before the program, in its namespace. CadQuery's own `Workplane.faces` and
# `Workplane.workplane` are wrapped; nothing else of CadQuery is touched.
PRELUDE = r"""
import json as _pj
import cadquery as _pcq
from OCP.Bnd import Bnd_Box as _PBox
from OCP.BRepBndLib import BRepBndLib as _PBnd
from OCP.BRep import BRep_Tool as _PTool
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf as _PProj


class ProbeRecord(BaseException):
    pass


_p_faces = _pcq.Workplane.faces
_p_workplane = _pcq.Workplane.workplane
_p_made = []


def _p_v(v):
    return [v.x, v.y, v.z]


def _p_box_centre(f):
    box = _PBox()
    _PBnd.AddOptimal_s(f.wrapped, box, False, False)
    lx, ly, lz, hx, hy, hz = box.Get()
    return [(lx + hx) / 2, (ly + hy) / 2, (lz + hz) / 2]


def _p_pick(keys, maximum, tol):
    # CadQuery's _NthSelector.cluster and filter (selectors.py), on indices.
    order = sorted(range(len(keys)), key=lambda i: keys[i])
    clusters = [[]]
    start = keys[order[0]]
    for i in order:
        if abs(keys[i] - start) <= tol:
            clusters[-1].append(i)
        else:
            clusters.append([i])
            start = keys[i]
    return sorted(clusters[-1] if maximum else clusters[0])


def _p_candidate(f, axis, key, box, com):
    lo = _PBox()
    _PBnd.AddOptimal_s(f.wrapped, lo, False, False)
    bounds = lo.Get()
    n = f.normalAt() if f.geomType() == "PLANE" else None
    return {
        "type": f.geomType(),
        "key": key,
        "area": f.Area(),
        "centre": _p_v(com),
        "low": bounds[axis],
        "high": bounds[axis + 3],
        "plane_normal": None if n is None else _p_v(n),
    }


def _p_face_fields(i, f, c, box):
    try:
        proj = _PProj(c.toPnt(), _PTool.Surface_s(f.wrapped))
        to_surface = proj.LowerDistance()
    except Exception as exc:
        to_surface = f"{type(exc).__name__}: {exc}"
    try:
        at_centre = _p_v(f.normalAt(c))
    except Exception as exc:
        at_centre = f"{type(exc).__name__}: {exc}"
    return {
        "index": i,
        "type": f.geomType(),
        "area": f.Area(),
        "centre": _p_v(c),
        "box_centre": box,
        "centre_to_surface": to_surface,
        "normal_at_centre": at_centre,
        "normal_at_mid_uv": _p_v(f.normalAt()),
    }


def _p_faces_record(selector, receiver, out):
    faces = receiver._collectProperty("Faces")
    axis = {"X": 0, "Y": 1, "Z": 2}[selector[1]]
    maximum = selector[0] == ">"
    com = [f.Center() for f in faces]
    box = [_p_box_centre(f) for f in faces]
    com_keys = [_p_v(c)[axis] for c in com]
    box_keys = [b[axis] for b in box]
    tol = 0.0001
    chosen = _p_pick(com_keys, maximum, tol)
    rest = [com_keys[i] for i in range(len(faces)) if i not in chosen]
    sel_keys = [com_keys[i] for i in chosen]
    if rest:
        gap = min(sel_keys) - max(rest) if maximum else min(rest) - max(sel_keys)
    else:
        gap = None
    picked = [_p_face_fields(i, faces[i], com[i], box[i]) for i in chosen]
    return {
        "selector": selector,
        "stack": [type(o).__name__ for o in receiver.objects],
        "candidates": len(faces),
        "candidate_types": sorted(f.geomType() for f in faces),
        "candidate_faces": [
            _p_candidate(f, axis, k, b, c) for f, k, b, c in zip(faces, com_keys, box, com)
        ],
        "selected": picked,
        "cadquery_order": [
            next(i for i, f in enumerate(faces) if f.isSame(o)) for o in out.objects
        ],
        "box_centre_selection": _p_pick(box_keys, maximum, tol),
        "box_centre_agrees": _p_pick(box_keys, maximum, tol) == chosen,
        "gap": gap,
        "spread": max(sel_keys) - min(sel_keys),
    }


def _p_selected_record(selector, receiver, out):
    # A selector that does not rank (a surface type, `%CYLINDER`): the faces it kept.
    faces = receiver._collectProperty("Faces")
    picked = []
    for o in out.objects:
        i = next(k for k, f in enumerate(faces) if f.isSame(o))
        picked.append(_p_face_fields(i, o, o.Center(), _p_box_centre(o)))
    return {
        "selector": selector,
        "stack": [type(o).__name__ for o in receiver.objects],
        "candidates": len(faces),
        "candidate_types": sorted(f.geomType() for f in faces),
        "selected": picked,
    }


def _p_faces_wrap(self, selector=None, tag=None):
    out = _p_faces(self, selector, tag)
    if isinstance(selector, str) and tag is None and len(selector) == 2:
        _p_made.append((out, _p_faces_record(selector, self, out)))
    elif isinstance(selector, str) and tag is None and selector.startswith("%"):
        _p_made.append((out, _p_selected_record(selector, self, out)))
    return out


def _p_workplane_wrap(self, *args, **kwargs):
    for made, record in _p_made:
        if made is self:
            record["workplane_args"] = [repr(a) for a in args]
            record["workplane_kwargs"] = sorted(kwargs)
            record["parent_origin"] = _p_v(self.plane.origin)
            try:
                new = _p_workplane(self, *args, **kwargs)
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            else:
                record["plane"] = {
                    "origin": _p_v(new.plane.origin),
                    "x": _p_v(new.plane.xDir),
                    "z": _p_v(new.plane.zDir),
                }
            raise ProbeRecord(_pj.dumps(record, sort_keys=True))
    return _p_workplane(self, *args, **kwargs)


_pcq.Workplane.faces = _p_faces_wrap
_pcq.Workplane.workplane = _p_workplane_wrap
"""

_HEAD = "import cadquery as cq\n\n"
_SHOW = "\nshow_object(result)\n"
# The same on y < 0.
_BELOW = 'cq.Workplane("XY").transformed(offset=cq.Vector(0, -15, 0)).box(30, 30, 30)'
# A box that takes away everything with x < 0 (the half of a part on x > 0 stays).
_HALF = 'cq.Workplane("XY").transformed(offset=cq.Vector(-15, 0, 0)).box(30, 30, 30)'
# Own programs, each a construction whose selection and plane have a closed form
# (`tests/fixtures/selectors/README.md` gives them).
CONSTRUCTED: dict[str, str] = {
    **{
        f"box{sel}": f'result = cq.Workplane("XY").box(2, 3, 4).faces("{sel}").workplane()'
        for sel in SELECTORS
    },
    **{
        f"box-off-origin{sel}": (
            'result = cq.Workplane("XY").transformed(offset=cq.Vector(5, -6, 7))'
            f'.box(2, 3, 4).faces("{sel}").workplane()'
        )
        for sel in SELECTORS
    },
    **{
        f"box-turned{sel}": (
            'result = cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 30))'
            f'.box(2, 3, 4).faces("{sel}").workplane()'
        )
        for sel in SELECTORS
    },
    **{
        f"cylinder{sel}": f'result = cq.Workplane("XY").cylinder(4, 1).faces("{sel}").workplane()'
        for sel in (">X", ">Z")
    },
    "half-cylinder>Z": (
        'result = (cq.Workplane("YZ").cylinder(4, 1)'
        '.cut(cq.Workplane("XY").box(10, 10, 10, centered=(True, True, False)).mirror("XY"))'
        '.faces(">Z").workplane())'
    ),
    "coplanar-tops>Z": (
        'result = (cq.Workplane("XY").box(10, 2, 1)'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1)).box(1, 2, 1))'
        '.faces(">Z").workplane())'
    ),
    "near-tie-inside>Z": (
        'result = (cq.Workplane("XY").box(10, 2, 1)'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1.00005)).box(1, 2, 1))'
        '.faces(">Z").workplane())'
    ),
    "near-tie-outside>Z": (
        'result = (cq.Workplane("XY").box(10, 2, 1)'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1.00015)).box(1, 2, 1))'
        '.faces(">Z").workplane())'
    ),
    **{
        f"near-tie-chain{sel}": (
            'result = (cq.Workplane("XY").box(10, 2, 1)'
            '.union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))'
            '.union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 1.00008)).box(1, 2, 1))'
            '.union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1.00016)).box(1, 2, 1))'
            f'.faces("{sel}").workplane())'
        )
        for sel in (">Z",)
    },
    "box-centre-not-mass>X": (
        'result = (cq.Workplane("XY").polyline([(0, 0), (4, 0), (0, 3)]).close().extrude(1)'
        '.faces(">X").workplane())'
    ),
    # plans/face-centre-of-mass step 1: faces of one surface that arris splits, a
    # near-tie's planes, and `workplane()` on one curved face of each kind.
    "seam-split-ring>Z": (
        'result = (cq.Workplane("YZ").cylinder(4, 5)'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(0, -11.5, 0)).box(5, 17, 4))'
        '.faces(">Z").workplane())'
    ),
    "slot-split-side>Y": (
        'result = (cq.Workplane("YZ").cylinder(4, 5)'
        '.cut(cq.Workplane("XY").box(6, 2, 20)).faces(">Y").workplane())'
    ),
    "slanted-coplanar>X": (
        'result = (cq.Workplane("XY").polyline([(0, 0), (4, 0), (6, 3), (0, 3)]).close()'
        ".extrude(10)"
        '.cut(cq.Workplane("XY").transformed(offset=cq.Vector(5, 1.5, 5)).box(6, 6, 2))'
        '.faces(">X").workplane())'
    ),
    "slanted-apart>X": (
        'result = (cq.Workplane("XY").polyline([(0, 0), (4, 0), (6, 3), (0, 3)]).close()'
        ".extrude(10)"
        '.cut(cq.Workplane("XY").transformed(offset=cq.Vector(5, 1.5, 5)).box(6, 6, 2))'
        '.cut(cq.Workplane("XY").transformed(offset=cq.Vector(5, 1.5, 9)).box(6, 6, 2))'
        '.faces(">X").workplane())'
    ),
    "half-cylinder-outer": (
        'result = (cq.Workplane("XY").cylinder(4, 2).cut(' + _HALF + ")"
        '.faces("%CYLINDER").workplane())'
    ),
    "half-bore": (
        'result = (cq.Workplane("XY").box(10, 10, 4, centered=(False, True, True))'
        '.cut(cq.Workplane("XY").cylinder(10, 2)).faces("%CYLINDER").workplane())'
    ),
    "half-cone": (
        'result = (cq.Workplane("XY").newObject([cq.Solid.makeCone(2, 1, 4)])'
        ".cut(" + _HALF + ').faces("%CONE").workplane())'
    ),
    "half-sphere": (
        'result = (cq.Workplane("XY").sphere(3).cut(' + _HALF + ').faces("%SPHERE").workplane())'
    ),
    "half-torus": (
        'result = (cq.Workplane("XY").newObject([cq.Solid.makeTorus(5, 1)])'
        ".cut(" + _HALF + ').faces("%TORUS").workplane())'
    ),
    "quarter-torus": (
        'result = (cq.Workplane("XY").newObject([cq.Solid.makeTorus(5, 1)])'
        ".cut(" + _HALF + ").cut(" + _BELOW + ').faces("%TORUS").workplane())'
    ),
    "whole-cylinder": 'result = cq.Workplane("XY").cylinder(4, 2).faces("%CYLINDER").workplane()',
    "whole-cone": (
        'result = cq.Workplane("XY").newObject([cq.Solid.makeCone(2, 1, 4)])'
        '.faces("%CONE").workplane()'
    ),
    "whole-sphere": 'result = cq.Workplane("XY").sphere(3).faces("%SPHERE").workplane()',
    "whole-torus": (
        'result = cq.Workplane("XY").newObject([cq.Solid.makeTorus(5, 1)])'
        '.faces("%TORUS").workplane()'
    ),
}


def constructed_programs() -> dict[str, str]:
    """The constructions as whole programs, by name."""
    return {name: _HEAD + body + _SHOW for name, body in sorted(CONSTRUCTED.items())}


# The selectors plans/lift-edges-and-blends declared: `edges` reads them, never `faces`.
_LATER_SELECTORS = ("|X", "|Y", "|Z", ">Z or <Z")


def before_subset() -> Subset:
    """The subset before the face selector bundle that admitted the 950 programs."""
    today = subset()
    # Forms added in later bundles admit programs outside the original 950.
    # Remove them from both sides of the historical reach comparison.
    later = {
        "Workplane.pushPoints",
        "Workplane.cboreHole",
        "Workplane.cskHole",
        "Workplane.rarray",
        "Workplane.polarArray",
        "Workplane.cutBlind",
        "Workplane.edges",
        "Workplane.fillet",
        "Workplane.chamfer",
        "Workplane.cutThruAll",
        "Workplane.center",
        "Workplane.rect",
        "Workplane.slot2D",
        "Workplane.loft",
        "Workplane.shell",
    }
    # Taper was lifted later on a call name the original bundle already used.
    extrude = CensusForm("Workplane.extrude", (("num",),), (("both", ("bool",)),))
    named = {form.name for form in BUNDLE} | later | {extrude.name}
    return Subset(
        forms=(extrude, *(form for form in today.forms if form.name not in named)),
        selectors=tuple(sorted(set(today.selectors) - set(SELECTORS) - set(_LATER_SELECTORS))),
        end_forms=today.end_forms,
    )


def bundle_subset() -> Subset:
    """`before_subset()` with this plan's declarations added."""
    before = before_subset()
    return Subset(
        forms=before.forms + BUNDLE,
        selectors=tuple(sorted({*before.selectors, *SELECTORS})),
        end_forms=before.end_forms,
    )


def newly_reached(census: Sequence[ProgramCensus | Unparsable]) -> list[str]:
    """The stems the bundle admits and `before_subset()` does not, sorted."""
    before = set(reach(census, before_subset()).stems)
    return sorted(set(reach(census, bundle_subset()).stems) - before)


def record_of(report: OracleReport) -> dict[str, Any] | None:
    """The probe's record carried in a runtime report's message, or None."""
    if report.status is not OracleStatus.RUNTIME:
        return None
    last = report.message.splitlines()[-1] if report.message else ""
    if not last.startswith(MARK):
        return None
    record: dict[str, Any] = json.loads(last[len(MARK) :])
    return record


def row(
    program: CorpusProgram, report: OracleReport, licence: str, revision: str
) -> dict[str, Any]:
    """One program's row: the original program's SHA-256, its outcome and the record."""
    record = record_of(report)
    return {
        "stem": program.stem,
        "family": program.family,
        "licence": licence,
        "revision": revision,
        "program_sha256": hashlib.sha256(program.text.encode("utf-8", "surrogatepass")).hexdigest(),
        "status": "record" if record is not None else report.status.value,
        "message": "" if record is not None else report.message,
        "record": record,
    }


def outcome(r: Mapping[str, Any]) -> str:
    """A row's outcome as `counts.json` keys it: the selection, its surface types and plane."""
    record = r["record"]
    if record is None:
        return f"status {r['status']}"
    types = "+".join(s["type"] for s in record["selected"])
    placed = "plane" if "plane" in record else f"error {record['error'].split(':')[0]}"
    box = "box-centre agrees" if record["box_centre_agrees"] else "box-centre differs"
    return f"{record['selector']} {len(record['selected'])} {types} {placed}, {box}"


def counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The rows counted by outcome and by family, every row counted."""
    by_outcome = Counter(outcome(r) for r in rows)
    by_family: dict[str, Counter[str]] = {}
    for r in rows:
        by_family.setdefault(r["family"], Counter())[outcome(r)] += 1
    return {
        "programs": len(rows),
        "outcomes": dict(sorted(by_outcome.items())),
        "families": {f: dict(sorted(c.items())) for f, c in sorted(by_family.items())},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--range", help="START:STOP of the sorted newly reached programs")
    parser.add_argument("--constructed", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--work-dir", type=pathlib.Path, default=pathlib.Path("selector-probe"))
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT)
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    args.work_dir.mkdir(parents=True, exist_ok=True)

    if args.constructed:
        constructions = constructed_programs()
        reports = oracle_run.run_many(
            [PRELUDE + text for text in constructions.values()],
            timeout=TIMEOUT,
            workers=args.workers,
        )
        out = [
            {
                "name": name,
                "program": text,
                "status": "record" if record_of(r) is not None else r.status.value,
                "record": record_of(r),
            }
            for (name, text), r in zip(constructions.items(), reports, strict=True)
        ]
        (args.work_dir / "constructed.json").write_text(
            json.dumps(out, sort_keys=True, indent=1) + "\n", encoding="utf-8"
        )
        print(f"{len(out)} constructions", file=sys.stderr)
    if args.range:
        from arris_gym.census import benchcad

        start, stop = (int(x) for x in args.range.split(":"))
        programs = benchcad.read()
        stems = set(newly_reached([census_program(p) for p in programs]))
        chosen = sorted((p for p in programs if p.stem in stems), key=lambda p: p.stem)
        part = chosen[start:stop]
        reports = oracle_run.run_many(
            [PRELUDE + p.text for p in part], timeout=TIMEOUT, workers=args.workers
        )
        rows = [
            row(p, r, benchcad.LICENCE, benchcad.REVISION)
            for p, r in zip(part, reports, strict=True)
        ]
        (args.work_dir / f"part-{start:05d}.json").write_text(
            json.dumps({"of": len(chosen), "start": start, "rows": rows}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{len(rows)} of {len(chosen)} probed from {start}", file=sys.stderr)
    if args.merge:
        parts = sorted(args.work_dir.glob("part-*.json"))
        merged: list[dict[str, Any]] = []
        total = None
        for path in parts:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["start"] != len(merged):
                raise ValueError(f"{path} starts at {data['start']}, not {len(merged)}")
            total = data["of"]
            merged.extend(data["rows"])
        if total is None or len(merged) != total:
            raise ValueError(f"the parts hold {len(merged)} rows of {total}")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in merged)
        (args.out_dir / "benchcad.jsonl.gz").write_bytes(gzip.compress(text.encode(), mtime=0))
        (args.out_dir / "counts.json").write_text(
            json.dumps(counts(merged), sort_keys=True, indent=1) + "\n", encoding="utf-8"
        )
        constructed = args.work_dir / "constructed.json"
        (args.out_dir / "constructed.json").write_text(
            constructed.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print(json.dumps(counts(merged)["outcomes"], indent=1), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
