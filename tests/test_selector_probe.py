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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import arris
import arris.build
import pytest

import arris_gym.cq as cq
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


# --- plans/face-centre-of-mass step 1: a face's centre of mass, on both kernels ---------

Vec = tuple[float, float, float]
# arris's `surface_properties(face).centroid` and Open CASCADE's `Center()` against the
# closed forms below, as a fraction of the face's sqrt(area) (arris's own tests hold the
# centre to that scale): the largest difference on any construction here is 1.5e-16 of
# it (a half cone, on the oracle), and this bound is about 7,000 times that.
CENTRE_ERROR = 1e-12


def one_solid(part: cq.Workplane) -> arris.build.Solid:
    (solid,) = part._solids()
    return solid


def surfaces(solid: arris.build.Solid, kind: str) -> list[tuple[arris.Face, float, Vec]]:
    """The faces of `kind` with arris's area and centre of mass, in the kernel's order."""
    model = solid.model
    out = []
    for face in model.faces(solid.body):
        if model.surface(face).kind == kind:
            props = model.surface_properties(face)
            out.append((face, props.area, props.centroid))
    return out


def shared_edge(solid: arris.build.Solid, a: arris.Face, b: arris.Face) -> bool:
    model = solid.model
    return bool({e.index for e in model.edges_of(a)} & {e.index for e in model.edges_of(b)})


def off(got: Sequence[float], want: Sequence[float], area: float) -> float:
    """The largest component difference of a centre, over the face's sqrt(area)."""
    return max(abs(p - q) for p, q in zip(got, want, strict=True)) / math.sqrt(area)


def unit(v: Sequence[float]) -> Vec:
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n, v[2] / n)


def slanted_x(normal: Sequence[float]) -> list[float]:
    """CadQuery's `_computeXdir` for any normal: (0, 0, 1) x normal, unit, else +x."""
    cross = (-normal[1], normal[0], 0.0)
    length = math.hypot(*cross)
    return (
        [cross[0] / length, cross[1] / length, 0.0]
        if length > probe_tolerance()
        else [1.0, 0.0, 0.0]
    )


def revolved_half_sphere() -> arris.build.Solid:
    """A hemisphere of radius 3 on x >= 0, about the z axis: a half disc turned by pi."""
    path = arris.build.Workplane.XZ().start((0, -3)).arc_to((0, 3), tangent=(1, 0))
    return path.close().revolve("y", math.pi)


# (name, kind, centre, area) of the one face each construction's selector keeps, by
# hand: 2r/pi for a half cylinder and 2r/pi again for a half bore (r = 2); a half cone
# (radii 2 and 1, height 4, slant sqrt(17)) has its radial centre (2/pi) * (integral
# of rho^2 dz) / (integral of rho dz) = (2/pi) * (14/9) and its height 16/9; a half
# sphere's is r/2; a quarter torus (R = 5, r = 1) has the radial centre R + r^2/(2R),
# on the bisector at 2/pi of it.
RHO = 5 + 1 / (2 * 5)
CURVED: dict[str, tuple[str, Vec, float]] = {
    "half-cylinder-outer": ("CYLINDER", (4 / math.pi, 0.0, 0.0), math.pi * 2 * 4),
    "half-bore": ("CYLINDER", (4 / math.pi, 0.0, 0.0), math.pi * 2 * 4),
    "half-cone": ("CONE", (2 / math.pi * 14 / 9, 0.0, 16 / 9), 1.5 * math.pi * math.sqrt(17)),
    "half-sphere": ("SPHERE", (1.5, 0.0, 0.0), 18 * math.pi),
    "quarter-torus": ("TORUS", (2 * RHO / math.pi, 2 * RHO / math.pi, 0.0), 5 * math.pi**2),
}
# The unit normal CadQuery's plane takes: the surface's outward normal at the foot of the
# centre, which is the centre's azimuth for a surface of revolution; a bore's faces the axis.
CURVED_NORMAL: dict[str, Vec] = {
    "half-cylinder-outer": (1.0, 0.0, 0.0),
    "half-bore": (-1.0, 0.0, 0.0),
    "half-cone": unit((4.0, 0.0, 1.0)),
    "half-sphere": (1.0, 0.0, 0.0),
    "quarter-torus": unit((-1.0, -1.0, 0.0)),
}


@pytest.mark.parametrize("name", sorted(CURVED))
def test_the_oracle_places_a_plane_through_a_curved_faces_centre(name: str) -> None:
    kind, centre, area = CURVED[name]
    record = constructed()[name]["record"]
    (face,) = record["selected"]
    assert face["type"] == kind
    assert face["area"] == pytest.approx(area, rel=1e-12)
    assert off(face["centre"], centre, area) <= CENTRE_ERROR
    # The plane's normal is the surface's at the centre's foot, its origin the parent's
    # (the world's) projected onto the plane through the centre, its x CadQuery's.
    n = CURVED_NORMAL[name]
    height = sum(c * m for c, m in zip(centre, n, strict=True))
    plane = record["plane"]
    assert close(plane["z"], list(n))
    assert close(plane["origin"], [height * m for m in n])
    assert close(plane["x"], slanted_x(n))


def arris_half(name: str) -> tuple[arris.build.Solid, str]:
    """The same part on arris, built as `arris.build` offers it, and its surface's kind."""
    half = arris.build.Solid.box((-30.0, -15.0, -15.0), (0.0, 15.0, 15.0))
    match name:
        case "half-cylinder-outer":
            cylinder = arris.build.Solid.cylinder((0, 0, -2), (0, 0, 1), 2, 4)
            return cylinder.cut(half), "cylinder"
        case "half-bore":
            block = arris.build.Solid.box((0.0, -5.0, -2.0), (10.0, 5.0, 2.0))
            return block.cut(arris.build.Solid.cylinder((0, 0, -5), (0, 0, 1), 2, 10)), "cylinder"
        case "half-cone":
            profile = arris.build.Workplane.XZ().polygon([(0, 0), (2, 0), (1, 4), (0, 4)])
            # Turned by pi about +z from +x it sweeps y >= 0; a quarter turn back puts it on x >= 0.
            return profile.revolve("y", math.pi).moved(angle=-math.pi / 2), "cone"
        case "half-sphere":
            return revolved_half_sphere().moved(angle=-math.pi / 2), "sphere"
        case "quarter-torus":
            circle = arris.build.Workplane.XZ().circle(1, center=(5, 0))
            return circle.revolve("y", math.pi / 2), "torus"
    raise AssertionError(name)


@pytest.mark.parametrize("name", sorted(CURVED))
def test_arris_gives_a_curved_faces_exact_area_and_centre(name: str) -> None:
    _, centre, area = CURVED[name]
    solid, kind = arris_half(name)
    found = surfaces(solid, kind)
    if kind == "cylinder":
        # arris holds the half cylinder as two quarter faces that share the seam's edge
        # (the area-weighted centre of the two is the half's).
        assert len(found) == 2
        assert shared_edge(solid, found[0][0], found[1][0])
        got_area = found[0][1] + found[1][1]
        got_centre = tuple(
            (found[0][1] * p + found[1][1] * q) / got_area
            for p, q in zip(found[0][2], found[1][2], strict=True)
        )
    else:
        ((_, got_area, got_centre),) = found
    assert got_area == pytest.approx(area, rel=1e-12)
    assert off(got_centre, centre, area) <= CENTRE_ERROR
    # arris and the oracle agree on the same face (their records differ from the closed
    # form by rounding only).
    record = constructed()[name]["record"]
    assert off(got_centre, record["selected"][0]["centre"], area) <= CENTRE_ERROR


def test_a_whole_surface_of_revolution_has_its_centre_on_its_axis_and_no_foot() -> None:
    """A cylinder, cone, sphere or torus face with no cut: the oracle's `workplane()` fails."""
    # The centres: the cylinder's and sphere's and torus's own, the cone's at 16/9 of its
    # height by the integral of z * rho over the integral of rho.
    centres = {
        "whole-cylinder": (0.0, 0.0, 0.0),
        "whole-cone": (0.0, 0.0, 16 / 9),
        "whole-sphere": (0.0, 0.0, 0.0),
        "whole-torus": (0.0, 0.0, 0.0),
    }
    for name, centre in centres.items():
        record = constructed()[name]["record"]
        (face,) = record["selected"]
        assert close(face["centre"], list(centre))
        assert record["error"] == (
            "StdFail_NotDone: GeomAPI_ProjectPointOnSurf::LowerDistanceParameters"
        )
        assert "plane" not in record
    # A half torus is two faces on Open CASCADE too (split at the seam of the tube), and
    # CadQuery refuses two curved faces.
    half = constructed()["half-torus"]["record"]
    assert [f["type"] for f in half["selected"]] == ["TORUS", "TORUS"]
    assert (
        half["error"] == "ValueError: If multiple objects selected, they all must be planar faces."
    )


def ring_part() -> arris.build.Solid:
    return one_solid(
        cq.Workplane("YZ")
        .cylinder(4, 5)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(0, -11.5, 0)).box(5, 17, 4))
    )


def slot_part() -> arris.build.Solid:
    return one_solid(cq.Workplane("YZ").cylinder(4, 5).cut(cq.Workplane("XY").box(6, 2, 20)))


def test_open_cascade_has_one_face_where_arris_has_two_that_share_an_edge() -> None:
    """The regression shape: a cylinder entered from -y by a box wider than it."""
    candidates = constructed()["seam-split-ring>Z"]["record"]["candidate_faces"]
    (cylinder,) = [c for c in candidates if c["type"] == "CYLINDER"]
    # By hand: the side's area less the window, an arc of half angle asin(2/5) over the
    # length 4; its centre is the window's, 5 sin(a)/a off, taken from the axis.
    a = math.asin(2 / 5)
    window = 2 * 5 * a * 4
    whole = 2 * math.pi * 5 * 4
    area = whole - window
    y = window * 5 * math.sin(a) / a / area
    assert cylinder["area"] == pytest.approx(area, rel=1e-12)
    assert off(cylinder["centre"], (0.0, y, 0.0), area) <= CENTRE_ERROR
    solid = ring_part()
    (up, down) = surfaces(solid, "cylinder")
    assert shared_edge(solid, up[0], down[0])
    assert up[1] + down[1] == pytest.approx(area, rel=1e-12)
    # The area-weighted centre of the two halves is Open CASCADE's one centre.
    both = tuple((up[1] * p + down[1] * q) / area for p, q in zip(up[2], down[2], strict=True))
    assert off(both, cylinder["centre"], area) <= CENTRE_ERROR
    # Each half's own centre is the whole's moved along the axis: the halves are 3.51 up and down.
    assert up[2][2] == pytest.approx(-down[2][2], abs=1e-12)
    assert abs(up[2][2]) > 1


def test_open_cascade_has_two_faces_where_arris_has_two_that_share_none() -> None:
    """A through slot cuts the side into two arcs, y > 1 and y < -1, apart."""
    candidates = constructed()["slot-split-side>Y"]["record"]["candidate_faces"]
    cylinders = [c for c in candidates if c["type"] == "CYLINDER"]
    # Each arc has half angle acos(1/5) about its own side, over the length 4.
    b = math.acos(1 / 5)
    area = 2 * 5 * b * 4
    y = 5 * math.sin(b) / b
    assert [round(c["centre"][1], 9) for c in cylinders] == [round(y, 9), round(-y, 9)]
    for c in cylinders:
        assert c["area"] == pytest.approx(area, rel=1e-12)
        assert off(c["centre"], (0.0, math.copysign(y, c["centre"][1]), 0.0), area) <= CENTRE_ERROR
    # arris cuts the +y arc at its seam, in two faces that share an edge; the -y arc is one.
    solid = slot_part()
    faces = surfaces(solid, "cylinder")
    assert len(faces) == 3
    (first, second) = [f for f in faces if f[2][1] > 0]
    (other,) = [f for f in faces if f[2][1] < 0]
    assert shared_edge(solid, first[0], second[0])
    assert not shared_edge(solid, first[0], other[0])
    assert not shared_edge(solid, second[0], other[0])
    assert first[1] + second[1] == pytest.approx(area, rel=1e-12)
    assert other[1] == pytest.approx(area, rel=1e-12)
    assert off(other[2], (0.0, -y, 0.0), area) <= CENTRE_ERROR


def test_a_slanted_pair_of_one_plane_and_the_oracle_s_plane_on_it() -> None:
    """Two planar faces of one slanted plane, with equal and with different areas.

    The face x = 3 + ... of the prism on (0,0) (4,0) (6,3) (0,3): its normal is
    (3, -2, 0) / sqrt(13). A notch splits it by z; a face's centre is its middle.
    """
    n = unit((3.0, -2.0, 0.0))
    for name, mids in (("slanted-coplanar>X", (2.0, 8.0)), ("slanted-apart>X", (2.0, 7.0))):
        record = constructed()[name]["record"]
        faces = record["selected"]
        assert [f["type"] for f in faces] == ["PLANE", "PLANE"]
        for f, z in zip(faces, mids, strict=True):
            assert close(f["centre"], [5.0, 1.5, z])
            assert close(f["normal_at_centre"], list(n))
        # The plane is the world origin's projection on the face's plane through (5, 1.5).
        height = 5 * n[0] + 1.5 * n[1]
        assert close(record["plane"]["origin"], [height * m for m in n])
        assert close(record["plane"]["z"], list(n))
        assert close(record["plane"]["x"], slanted_x(n))
    # arris's centres, for the same part: the face's middle, whichever way it is computed.
    part = one_solid(
        cq.Workplane("XY")
        .polyline([(0, 0), (4, 0), (6, 3), (0, 3)])
        .close()
        .extrude(10)
        .cut(cq.Workplane("XY").transformed(offset=cq.Vector(5, 1.5, 5)).box(6, 6, 2))
    )
    slanted = [s for s in surfaces(part, "plane") if abs(s[2][0] - 5.0) < 1e-9]
    assert sorted(round(s[2][2], 9) for s in slanted) == [2.0, 8.0]
    for _, area, centre in slanted:
        assert area == pytest.approx(math.sqrt(13) * 4, rel=1e-12)
        assert centre[1] == pytest.approx(1.5, abs=1e-12)


def test_arris_gives_the_near_ties_areas_for_the_area_weighted_offset() -> None:
    """The near tie's two top planes, 5e-5 apart: their areas 4 and 2 weigh the offset."""
    part = one_solid(
        cq.Workplane("XY")
        .box(10, 2, 1)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1.00005)).box(1, 2, 1))
    )
    tops = [
        s
        for s in surfaces(part, "plane")
        if abs(s[2][2] - 1.5) < 1e-3 and abs(s[2][1]) < 1e-9 and abs(s[2][0]) > 1
    ]
    heights = sorted((round(s[2][2], 9), round(s[1], 9)) for s in tops)
    assert heights == [(1.5, 4.0), (1.50005, 2.0)]
    offset = sum(z * a for z, a in heights) / sum(a for _, a in heights)
    assert offset == pytest.approx(1.5 + 0.00005 / 3, abs=1e-12)
