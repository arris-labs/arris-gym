"""ADR-0017's evidence: the selector probe's committed rows hold what the ADR says of them.

The rows come from the oracle (`tools/cq_selector_probe.py`, outside the gate);
these tests read only the committed files and the committed census, offline.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

import cq_selector_probe as probe
from arris_gym.census import ProgramCensus, Unparsable
from arris_gym.fidelity import OracleReport

FIXTURES = Path(__file__).parent / "fixtures"
SELECTORS = FIXTURES / "selectors"
PROGRAMS = FIXTURES / "c2" / "benchcad" / "programs.jsonl.gz"
# Open CASCADE's centre of mass and `projectToPlane` carry rounding: the plane's
# origin sits within 1.8e-15 of the closed form on the corpus. A unit vector's
# components are compared to the same bound.
ROUNDING = 1e-14
AXES = {"X": 0, "Y": 1, "Z": 2}


def rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in gzip.decompress((SELECTORS / "benchcad.jsonl.gz").read_bytes()).splitlines()
    ]


def constructed() -> dict[str, dict[str, Any]]:
    data = json.loads((SELECTORS / "constructed.json").read_text(encoding="utf-8"))
    return {c["name"]: c for c in data}


def census() -> tuple[list[ProgramCensus | Unparsable], dict[str, dict[str, Any]]]:
    out: list[ProgramCensus | Unparsable] = []
    records = {}
    for line in gzip.decompress(PROGRAMS.read_bytes()).splitlines():
        record = json.loads(line)
        records[record["census"]["stem"]] = record
        try:
            out.append(ProgramCensus.model_validate(record["census"]))
        except ValueError:
            out.append(Unparsable.model_validate(record["census"]))
    return out, records


def axis_unit(selector: str) -> list[float]:
    v = [0.0, 0.0, 0.0]
    v[AXES[selector[1]]] = 1.0 if selector[0] == ">" else -1.0
    return v


def x_dir(normal: list[float]) -> list[float]:
    """CadQuery's `_computeXdir`: (0, 0, 1) x normal, else +x, for an axis normal."""
    cross = [-normal[1], normal[0], 0.0]
    return cross if math.hypot(*cross) > 0 else [1.0, 0.0, 0.0]


def close(a: list[float], b: list[float]) -> bool:
    return all(abs(p - q) <= ROUNDING for p, q in zip(a, b, strict=True))


def test_the_rows_are_the_950_programs_the_bundle_adds() -> None:
    programs, records = census()
    stems = probe.newly_reached(programs)
    assert len(stems) == 950
    got = rows()
    assert [r["stem"] for r in got] == stems
    for r in got:
        source = records[r["stem"]]
        assert r["program_sha256"] == source["program_sha256"]
        assert (r["family"], r["licence"], r["revision"]) == (
            source["family"],
            source["licence"],
            source["revision"],
        )


def test_counts_are_the_rows_counted() -> None:
    committed = json.loads((SELECTORS / "counts.json").read_text(encoding="utf-8"))
    assert committed == probe.counts(rows())
    assert committed["programs"] == 950


def test_every_program_selects_planar_faces_normal_to_its_axis() -> None:
    selected: Counter[int] = Counter()
    for r in rows():
        record = r["record"]
        assert r["status"] == "record"
        assert "error" not in record
        assert record["workplane_args"] == []
        assert record["workplane_kwargs"] == []
        assert record["box_centre_agrees"]
        assert sorted(record["cadquery_order"]) == [s["index"] for s in record["selected"]]
        n = axis_unit(record["selector"])
        for face in record["selected"]:
            assert face["type"] == "PLANE"
            assert close(face["normal_at_centre"], n)
        selected[len(record["selected"])] += 1
    assert selected == {1: 910, 2: 40}
    assert {r["family"] for r in rows() if len(r["record"]["selected"]) == 2} == {"connecting_rod"}


def test_the_plane_is_the_parent_origin_moved_onto_the_face() -> None:
    for r in rows():
        record = r["record"]
        axis = AXES[record["selector"][1]]
        n = axis_unit(record["selector"])
        offsets = [face["centre"][axis] for face in record["selected"]]
        assert record["spread"] == max(offsets) - min(offsets) <= ROUNDING
        origin = list(record["parent_origin"])
        origin[axis] = offsets[0]
        plane = record["plane"]
        assert close(plane["origin"], origin)
        assert close(plane["z"], n)
        assert close(plane["x"], x_dir(n))


def test_no_ranking_is_near_a_tie() -> None:
    gaps = [r["record"]["gap"] for r in rows()]
    assert None not in gaps
    assert min(gaps) == pytest.approx(0.04, abs=ROUNDING)


def test_every_face_off_the_axis_sits_well_inside_the_cluster_boundary() -> None:
    """A face whose plane is not normal to the axis has its centre at least 0.5% of the
    part's extent along the axis away from the selected cluster's boundary."""
    least = math.inf
    for r in rows():
        record = r["record"]
        axis = AXES[record["selector"][1]]
        top = record["selector"][0] == ">"
        keys = [face["centre"][axis] for face in record["selected"]]
        boundary = (min(keys) - probe_tolerance()) if top else (max(keys) + probe_tolerance())
        faces = record["candidate_faces"]
        extent = max(f["high"] for f in faces) - min(f["low"] for f in faces)
        for f in faces:
            normal = f["plane_normal"]
            if normal is not None and abs(abs(normal[axis]) - 1) <= ROUNDING:
                continue
            least = min(least, ((boundary - f["key"]) if top else (f["key"] - boundary)) / extent)
    assert least > 0.005


def probe_tolerance() -> float:
    """CadQuery's selector tolerance as the probe's prelude writes it."""
    marker = "tol = "
    line = next(x for x in probe.PRELUDE.splitlines() if x.strip().startswith(marker))
    return float(line.split(marker)[1])


def test_constructions_have_their_closed_forms() -> None:
    c = constructed()
    assert sorted(c) == sorted(probe.CONSTRUCTED)
    for sel in probe.SELECTORS:
        # A 2 x 3 x 4 box centred on the origin, and on (5, -6, 7): the face's offset.
        axis = AXES[sel[1]]
        half = (1.0, 1.5, 2.0)[axis] * (1 if sel[0] == ">" else -1)
        n = axis_unit(sel)
        for name, centre in (
            (f"box{sel}", [0.0, 0.0, 0.0]),
            (f"box-off-origin{sel}", [5.0, -6.0, 7.0]),
        ):
            plane = c[name]["record"]["plane"]
            origin = list(centre)
            origin[axis] += half
            assert close(plane["origin"], origin)
            assert close(plane["z"], n)
            assert close(plane["x"], x_dir(n))
    # The half cylinder: its one curved face's centre of mass is 2r/pi off the axis, and
    # the plane passes through it, not through the surface.
    half = c["half-cylinder>Z"]["record"]
    assert [f["type"] for f in half["selected"]] == ["CYLINDER"]
    assert not half["box_centre_agrees"]
    assert close(half["plane"]["origin"], [0.0, 0.0, 2 / math.pi])
    # Coplanar tops: one plane; a near tie inside the tolerance: the area-weighted offset.
    assert close(c["coplanar-tops>Z"]["record"]["plane"]["origin"], [0.0, 0.0, 1.5])
    inside = c["near-tie-inside>Z"]["record"]
    assert len(inside["selected"]) == 2
    assert close(inside["plane"]["origin"], [0.0, 0.0, (4 * 1.5 + 2 * 1.50005) / 6])
    # Outside the tolerance, and a chain of steps each inside it: only the top face.
    for name, z in (("near-tie-outside>Z", 1.50015), ("near-tie-chain>Z", 1.50016)):
        record = c[name]["record"]
        assert len(record["selected"]) == 1
        assert close(record["plane"]["origin"], [0.0, 0.0, z])
    # A full cylinder's three faces tie on >X; a prism's two faces tie, not coplanar.
    assert c["cylinder>X"]["record"]["error"] == (
        "ValueError: If multiple objects selected, they all must be planar faces."
    )
    triangle = c["box-centre-not-mass>X"]["record"]
    assert triangle["error"] == "ValueError: Selected faces must be co-planar."
    assert not triangle["box_centre_agrees"]


def test_a_record_is_read_from_its_runtime_message_only() -> None:
    sha = hashlib.sha256(b"x").hexdigest()
    versions = {"cadquery": "2.3.0", "ocp": "7.9.3.0", "python": "3.12.0"}

    def report(status: str, message: str) -> OracleReport:
        return OracleReport.model_validate(
            {
                "status": status,
                "message": message,
                "measures": None,
                "step_sha256": None,
                "program_sha256": sha,
                "versions": versions,
            }
        )

    assert probe.record_of(report("runtime", 'ProbeRecord: {"a": 1}')) == {"a": 1}
    assert probe.record_of(report("runtime", "ValueError: no")) is None
    assert probe.record_of(report("syntax", 'ProbeRecord: {"a": 1}')) is None
