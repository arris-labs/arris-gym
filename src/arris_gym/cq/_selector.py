"""CadQuery's axis selectors over arris: which faces `faces(">Z")` keeps, and the plane on them.

ADR-0017 and ADR-0022 for faces, and ADR-0020 for edges. Private: `Workplane.faces`,
`Workplane.workplane`, `Workplane.edges`, `Workplane.fillet` and `Workplane.chamfer` call it.
"""

from __future__ import annotations

import itertools
import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass

import arris
import arris.build

from arris_gym.cq._unsupported import UnsupportedApi

__all__ = [
    "AXIS_SELECTORS",
    "CQ_TOLERANCE",
    "NO_FACES",
    "NO_SUITABLE_EDGES",
    "OR_SELECTORS",
    "PARALLEL_SELECTORS",
    "SELECTORS",
    "Edges",
    "Faces",
    "Seam",
    "edges_of_faces",
    "edges_of_solid",
    "plane_on",
    "plane_on_faces",
    "seams_of",
    "select_edges",
    "select_faces",
]

# The axis selectors the subset admits: `DirectionMinMaxSelector` on one world
# axis, `>` the furthest cluster and `<` the nearest (ADR-0017).
AXIS_SELECTORS = (">X", "<X", ">Y", "<Y", ">Z", "<Z")
# The selectors only `edges` reads (ADR-0020): `ParallelDirSelector` on a world
# axis, and `SumSelector` of the two ends of the z axis, `'>Z or <Z'`. No corpus
# program writes either on `faces`, so `faces` still refuses them.
PARALLEL_SELECTORS = ("|X", "|Y", "|Z")
OR_SELECTORS = (">Z or <Z",)
# Every selector string the subset declares, once for both methods (ADR-0012).
SELECTORS = (*AXIS_SELECTORS, *PARALLEL_SELECTORS, *OR_SELECTORS)
_AXIS = {"X": 0, "Y": 1, "Z": 2}

# CadQuery 2.3.0's default tolerance for `DirectionMinMaxSelector`, for
# `Workplane._computeXdir` and for `_isCoPlanar`: faces whose keys lie within it
# of a cluster's first key tie, and a normal shorter than it is no direction.
# ADR-0017 rule 1. In model units.
CQ_TOLERANCE = 1e-4
# `_pick` compares keys after summing and subtracting them in floats, so a
# difference worked out one way can fall a few ulps (of keys under 1) on the
# other side of `CQ_TOLERANCE` from the same difference worked out another.
# `_pick_widths` keeps this much clear of that edge: a selection within it is
# refused, as one the margin could change. In model units.
_FLOAT_SLACK = 1e-12
# Quadrature error per sqrt(face area), bounded by ADR-0022 rule 1.
_CENTRE_ERROR = 1e-12
# Minimum projection distance per sqrt(face area) for at most 1e-9
# directional error from the centre (ADR-0022 rule 4).
_FOOT_MIN = 1e-3
# Open CASCADE's projection failure on a whole curved face, raised here as
# RuntimeError (ADR-0022 rule 4; see runtime-faces-workplane-no-foot).
_NO_FOOT = "StdFail_NotDone: GeomAPI_ProjectPointOnSurf::LowerDistanceParameters"
# Edge polyline chord and centre error as fractions of the solid's box diagonal
# (ADR-0020 rule 2).
_EDGE_CHORD = 1e-5
_EDGE_MARGIN = 1e-4


_FaceGroup = tuple[arris.Face, ...]


@dataclass(frozen=True)
class Faces:
    """The solid on the stack and its selected unified faces (ADR-0022 rule 2).

    Groups are in ascending key, with ties in kernel face order. Each group's
    members are also in kernel face order.
    """

    solid: arris.build.Solid
    groups: tuple[_FaceGroup, ...]


@dataclass(frozen=True)
class Edges:
    """The edges a selector kept, on a stack: the solid they belong to and the edges.

    The edges are the solid's own `arris.Edge` values, in CadQuery's order:
    ascending by their key along the selector's axis, a tie in the kernel's
    edge order. Only `edges`, `fillet` and `chamfer` read it (ADR-0020 rule 6).
    """

    solid: arris.build.Solid
    edges: tuple[arris.Edge, ...]


@dataclass(frozen=True)
class Seam:
    """Where Open CASCADE puts the seam of a cylinder `cq` built as CadQuery builds it.

    The cylinder has `radius` about the line through `point` along the unit
    `axis`; its seam is the line on it `radius` from the axis towards the unit
    `side`, across the axis (ADR-0020 rule 2, amended). CadQuery makes every
    such cylinder in its workplane's own axes and moves it there, and Open
    CASCADE starts a circle, and so the face it sweeps, at its frame's x: so
    `cylinder` and the circles `extrude` and `cutBlind` sweep have their seam
    on the workplane's +x, and a bore (`hole`, `cboreHole`, `cskHole`), swept
    along -z, on its -x. arris places its own seams by its own rule.
    """

    point: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius: float
    side: tuple[float, float, float]


def seams_of(tool: arris.build.Solid, side: Sequence[float]) -> tuple[Seam, ...] | None:
    """The seam of each cylinder face of `tool`, on `side`; `None` if one has no seam.

    `tool` is a cylinder or a circle swept along its plane's normal, built the
    way CadQuery builds it, `side` the workplane's x (or -x for a bore). A
    cylinder face with no seam (a sweep of an arc) is a part of a turn that
    Open CASCADE may later join with another into a face whose seam lies
    where neither says: `None`, no seam of the chain is known.
    """
    model = tool.model
    found: list[Seam] = []
    for face in model.faces(tool.body):
        info = model.surface(face)
        if info.kind != "cylinder":
            continue
        if info.origin is None or info.axis is None or info.radius is None:
            return None
        if not any(len(model.faces_of(tool.body, e)) == 1 for e in model.edges_of(face)):
            return None
        found.append(Seam(info.origin, info.axis, info.radius, (side[0], side[1], side[2])))
    return tuple(found)


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(v: Sequence[float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _pick(keys: Sequence[float], maximum: bool) -> list[int]:
    """The indices CadQuery's `DirectionMinMaxSelector` keeps among `keys`.

    The keys are sorted ascending (a stable sort), grouped greedily into
    clusters that each take every next key within `CQ_TOLERANCE` of the
    cluster's first, and `>` keeps the last cluster, `<` the first.
    """
    clusters: list[list[int]] = []
    start = 0.0
    for i in sorted(range(len(keys)), key=lambda j: keys[j]):
        if clusters and keys[i] - start <= CQ_TOLERANCE:
            clusters[-1].append(i)
        else:
            clusters.append([i])
            start = keys[i]
    return clusters[-1] if maximum else clusters[0]


def _cell(d: float) -> tuple[bool, bool, bool, bool]:
    """Where a difference `d` of two keys falls among the comparisons `_pick` makes of it."""
    return (d > CQ_TOLERANCE, d > 0.0, d < 0.0, d < -CQ_TOLERANCE)


def _pick_widths(keys: Sequence[float], width: Sequence[float], maximum: bool) -> list[int] | None:
    """What `_pick` keeps if it keeps the same under every shift of an uncertain key.

    A key `keys[i]` lies in `[keys[i] - width[i], keys[i] + width[i]]`.

    An exact key is a point (width 0), and `_pick` looks at a pair of keys only
    through their order and whether they lie within `CQ_TOLERANCE`. So its
    answer holds over the whole
    box when no such comparison can change; or when the keys whose comparisons
    can change (the connected sets of such pairs) each lie within
    `CQ_TOLERANCE` of one another at the worst and every other key compares
    the same way to all of a set's members: the set then acts as one key.
    A key below a gap that every shift keeps wider than `CQ_TOLERANCE` (above,
    for `<`) cannot reach the kept cluster, which starts at the first key past
    the gap; only the keys on the kept side of the widest such gap are checked.
    Returns `None` where none of this can be shown.
    """
    ranked = sorted(range(len(keys)), key=lambda j: keys[j], reverse=maximum)
    block = len(ranked)
    for cut in range(1, len(ranked)):
        near, far = ranked[:cut], ranked[cut:]
        if maximum:
            clear = min(keys[i] - width[i] for i in near) - max(keys[i] + width[i] for i in far)
        else:
            clear = min(keys[i] - width[i] for i in far) - max(keys[i] + width[i] for i in near)
        if clear > CQ_TOLERANCE:
            block = cut
            break
    near = ranked[:block]

    def cell(i: int, j: int) -> tuple[bool, bool, bool, bool] | None:
        """The comparisons of `keys[j] - keys[i]` if no shift changes them."""
        d = keys[j] - keys[i]
        reach = width[i] + width[j]
        low, high = _cell(d - reach - _FLOAT_SLACK), _cell(d + reach + _FLOAT_SLACK)
        return low if low == high else None

    parent = {i: i for i in near}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(near, 2):
        if (width[i] or width[j]) and cell(i, j) is None:
            parent[find(i)] = find(j)
    sets: dict[int, list[int]] = {}
    for i in near:
        sets.setdefault(find(i), []).append(i)
    for members in sets.values():
        if len(members) == 1:
            continue
        for i, j in itertools.permutations(members, 2):
            if abs(keys[j] - keys[i]) + width[i] + width[j] > CQ_TOLERANCE - _FLOAT_SLACK:
                return None
        for k in near:
            if k not in members and len({cell(m, k) for m in members}) != 1:
                return None
    return _pick(keys, maximum)


def _face_groups(model: arris.Model, faces: Sequence[arris.Face]) -> list[_FaceGroup]:
    """Connected faces of one surface and sense, in kernel face order."""
    by_edge: dict[int, list[int]] = {}
    infos = [model.surface(face) for face in faces]
    parents = list(range(len(faces)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for i, face in enumerate(faces):
        # A seam can be visited twice on one face. It cannot join two faces.
        for edge in dict.fromkeys(edge.index for edge in model.edges_of(face)):
            neighbours = by_edge.setdefault(edge, [])
            for j in neighbours:
                if _same_surface(infos[i], infos[j], face.reversed == faces[j].reversed, model):
                    parents[find(i)] = find(j)
            neighbours.append(i)
    groups: dict[int, list[arris.Face]] = {}
    for i, face in enumerate(faces):
        groups.setdefault(find(i), []).append(face)
    return [tuple(group) for group in groups.values()]


def select_faces(
    solid: arris.build.Solid, selector: str, among: Sequence[_FaceGroup] | None = None
) -> tuple[_FaceGroup, ...]:
    """The unified faces that CadQuery's axis selector keeps (ADR-0022).

    With `among`, ranks only the groups a preceding selector kept.
    A singleton planar face normal to the axis has its exact plane offset.
    Other keys are area-weighted centres projected onto the axis. Raises
    `UnsupportedApi` if the quadrature bound can change the selection.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> [(top,)] = select_faces(box, ">Z")
    >>> box.model.surface(top).origin
    (0.0, 0.0, 6.0)
    """
    maximum = selector[0] == ">"
    axis = _AXIS[selector[1]]
    unit = tuple(1.0 if i == axis else 0.0 for i in range(3))
    model = solid.model
    faces = model.faces(solid.body)
    if among is None:
        groups = _face_groups(model, faces)
    else:
        order = {face.index: i for i, face in enumerate(faces)}
        groups = sorted(among, key=lambda group: order[group[0].index])
    keys: list[float] = []
    widths: list[float] = []
    for group in groups:
        info = model.surface(group[0])
        if (
            len(group) == 1
            and info.kind == "plane"
            and info.normal is not None
            and info.origin is not None
            and _length(_cross(info.normal, unit)) <= model.angular_tolerance
        ):
            keys.append(info.origin[axis])
            widths.append(0.0)
        else:
            area, centre = _group_properties(model, group)
            keys.append(centre[axis])
            widths.append(_CENTRE_ERROR * math.sqrt(area))
    kept = _pick_widths(keys, widths, maximum) if any(widths) else _pick(keys, maximum)
    if kept is None:
        raise UnsupportedApi(
            f"Workplane.faces({selector!r}): the face key error bound can change the selection"
        )
    return tuple(groups[k] for k in _ordered(kept, keys))


def _group_properties(
    model: arris.Model, group: _FaceGroup
) -> tuple[float, tuple[float, float, float]]:
    properties = [model.surface_properties(face) for face in group]
    if len(properties) == 1:
        return properties[0].area, properties[0].centroid
    area = sum(p.area for p in properties)
    return area, (
        sum(p.area * p.centroid[0] for p in properties) / area,
        sum(p.area * p.centroid[1] for p in properties) / area,
        sum(p.area * p.centroid[2] for p in properties) / area,
    )


def _ordered(kept: Sequence[int], keys: Sequence[float]) -> list[int]:
    """`kept` in ascending key, a tie in the order given."""
    return sorted(kept, key=lambda k: keys[k])


# --- edges (ADR-0020) -------------------------------------------------------


def edges_of_solid(solid: arris.build.Solid) -> tuple[arris.Edge, ...]:
    """The candidate edges of `solid`, in the kernel's order (ADR-0020 rule 1).

    A `degenerate` edge is left out, as CadQuery's `Edges()` leaves out a
    degenerated edge (a sphere's pole).
    """
    model = solid.model
    return tuple(e for e in model.edges(solid.body) if model.curve(e).kind != "degenerate")


def edges_of_faces(
    solid: arris.build.Solid, groups: Sequence[_FaceGroup]
) -> tuple[tuple[arris.Edge, ...], frozenset[int]]:
    """The edges of the unified faces, each once and in first-encounter order.

    An edge joining members of one group is absent after CadQuery's cleaning.
    Each candidate is the solid's own edge value (ADR-0020 rule 1).
    The second result marks boundary edges that may join where an inner edge
    ends (see unsupported-edges-unified-face-boundary).
    """
    model = solid.model
    own = {e.index: e for e in edges_of_solid(solid)}
    found: dict[int, arris.Edge] = {}
    fragments: set[int] = set()
    for group in groups:
        first: dict[int, int] = {}
        inner: set[int] = set()
        for face in group:
            for edge in model.edges_of(face):
                if first.setdefault(edge.index, face.index) != face.index:
                    inner.add(edge.index)
        boundary = [own[index] for index in first if index in own and index not in inner]
        for edge in boundary:
            found.setdefault(edge.index, edge)
        if inner:
            vertices = {
                v.index for index in inner if index in own for v in model.vertices_of(own[index])
            }
            at_vertex: dict[int, list[arris.Edge]] = {}
            for edge in boundary:
                for v in model.vertices_of(edge):
                    if v.index in vertices:
                        at_vertex.setdefault(v.index, []).append(edge)
            for adjacent in at_vertex.values():
                for a, b in itertools.combinations(adjacent, 2):
                    if a != b and _may_join(model, a, b):
                        fragments.update((a.index, b.index))
    return tuple(found.values()), frozenset(fragments)


def _may_join(model: arris.Model, a: arris.Edge, b: arris.Edge) -> bool:
    """Whether boundary edges meeting at a vertex may be on the same curve."""
    p, q = model.curve(a), model.curve(b)
    if p.kind != q.kind:
        return False
    if p.axis is None or q.axis is None:
        return True
    if _length(_cross(p.axis, q.axis)) > model.angular_tolerance:
        return False
    if p.kind == "line":
        return True
    if p.kind == "circle":
        assert p.origin is not None
        assert q.origin is not None
        assert p.radius is not None
        assert q.radius is not None
        return (
            _length(_sub(p.origin, q.origin)) <= model.tolerance
            and abs(p.radius - q.radius) <= model.tolerance
        )
    return True


def _sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _exact_centre(model: arris.Model, edge: arris.Edge) -> tuple[float, float, float] | None:
    """The centre of mass of `edge` where it is known exactly, else `None` (ADR-0020 rule 2).

    A line's midpoint; a full circle's or full ellipse's centre; an arc's
    centre moved `r sin(θ/2)/(θ/2)` along its bisector. The arc runs
    counter-clockwise about the circle's axis from its start to its end, from
    its end to its start on a reversed edge. An ellipse arc and a B-spline
    edge have no exact centre here.
    """
    c = model.curve(edge)
    if c.kind == "line":
        return (
            (c.start[0] + c.end[0]) / 2,
            (c.start[1] + c.end[1]) / 2,
            (c.start[2] + c.end[2]) / 2,
        )
    if c.kind in ("circle", "ellipse") and c.start == c.end and c.origin is not None:
        return c.origin
    if c.kind != "circle" or c.origin is None or c.axis is None:
        return None
    first, last = (c.end, c.start) if edge.reversed else (c.start, c.end)
    u, v = _sub(first, c.origin), _sub(last, c.origin)
    sweep = math.atan2(_dot(_cross(u, v), c.axis), _dot(u, v))
    if sweep <= 0:
        sweep += 2 * math.pi
    # The bisector: u turned by half the sweep about the axis (Rodrigues; u is
    # perpendicular to the axis).
    half = sweep / 2
    w = _cross(c.axis, u)
    bisector = [u[k] * math.cos(half) + w[k] * math.sin(half) for k in range(3)]
    d = math.sin(half) / half
    return (
        c.origin[0] + d * bisector[0],
        c.origin[1] + d * bisector[1],
        c.origin[2] + d * bisector[2],
    )


def _polyline_centres(
    model: arris.Model, body: arris.Body, chord: float
) -> dict[int, tuple[float, float, float]]:
    """The centre of mass of each edge's tessellated polyline, by edge index.

    Summed in polyline order in Python floats, so it has the same bits on
    every machine (ADR-0020 rule 2).
    """
    mesh = model.tessellate(body, chord)
    points = struct.unpack(f"<{3 * mesh.n_positions}d", mesh.positions)
    indices = struct.unpack(f"<{len(mesh.edge_indices) // 4}I", mesh.edge_indices)
    found: dict[int, tuple[float, float, float]] = {}
    for edge, first, end in mesh.edges:
        total = 0.0
        weighted = [0.0, 0.0, 0.0]
        for k in range(first, end - 1):
            p = points[3 * indices[k] : 3 * indices[k] + 3]
            q = points[3 * indices[k + 1] : 3 * indices[k + 1] + 3]
            length = math.dist(p, q)
            total += length
            for j in range(3):
                weighted[j] += length * (p[j] + q[j]) / 2.0
        if total == 0.0:
            raise UnsupportedApi("Workplane.edges: an edge with no length in the mesh")
        found[edge.index] = (weighted[0] / total, weighted[1] / total, weighted[2] / total)
    return found


def _placed_key(
    model: arris.Model, info: arris.SurfaceInfo, axis: int, seams: Sequence[Seam] | None
) -> float | None:
    """A seam's key where the chain's records place it as Open CASCADE does, else `None`.

    ADR-0020 rule 2, amended: only on a cylinder whose axis is square to the
    selector's, so that every line along it has the key of the axis plus the
    side's share of the radius; and only where the records of that cylinder
    (its radius and axis line within the model's tolerance) all name one side.
    `seams` is `None` where the chain made a seam no record places.
    """
    if seams is None or info.kind != "cylinder":
        return None
    if info.origin is None or info.axis is None or info.radius is None:
        return None
    if info.axis[axis] != 0.0:
        return None
    sides: list[tuple[float, float, float]] = []
    for seam in seams:
        if abs(seam.radius - info.radius) > model.tolerance:
            continue
        if _length(_cross(seam.axis, info.axis)) > model.angular_tolerance:
            continue
        v = _sub(info.origin, seam.point)
        along = _dot(v, seam.axis)
        if _length([v[k] - along * seam.axis[k] for k in range(3)]) > model.tolerance:
            continue
        sides.append(seam.side)
    if not sides:
        return None
    if any(_length(_sub(side, sides[0])) > model.angular_tolerance for side in sides[1:]):
        return None
    return info.origin[axis] + info.radius * sides[0][axis]


def _edge_keys(
    solid: arris.build.Solid,
    edges: Sequence[arris.Edge],
    axis: int,
    seams: Sequence[Seam] | None = None,
) -> tuple[list[float], list[float]]:
    """Each edge's key along `axis` and how far it is trusted (ADR-0020 rule 2).

    A width of 0 is an exact key. A seam's key is exact where its face is a
    surface of revolution about an axis parallel to `axis`, or where `seams`
    place it as Open CASCADE does (`_placed_key`); else it lies anywhere on its
    face, so it is the face's box (centre, half the extent).
    An ellipse arc's or a B-spline edge's key is its polyline's centre of
    mass at a margin of the solid's box diagonal.
    """
    model = solid.model
    unit = tuple(1.0 if i == axis else 0.0 for i in range(3))
    whole = model.bounds(solid.body)
    if whole is None:
        raise UnsupportedApi("Workplane.edges on a solid without a box")
    diagonal = _length([whole[1][k] - whole[0][k] for k in range(3)])
    keys: list[float] = []
    widths: list[float] = []
    polylines: dict[int, tuple[float, float, float]] | None = None
    for edge in edges:
        centre = _exact_centre(model, edge)
        faces = model.faces_of(solid.body, edge)
        if len(faces) == 1:
            info = model.surface(faces[0])
            along = (
                info.axis is not None
                and _length(_cross(info.axis, unit)) <= model.angular_tolerance
            )
            if not (along and centre is not None):
                placed = _placed_key(model, info, axis, seams)
                if placed is not None:
                    keys.append(placed)
                    widths.append(0.0)
                    continue
                box = model.bounds(faces[0])
                if box is None:
                    raise UnsupportedApi("Workplane.edges on a seam of a face without a box")
                keys.append((box[0][axis] + box[1][axis]) / 2.0)
                widths.append((box[1][axis] - box[0][axis]) / 2.0)
                continue
        if centre is None:
            if polylines is None:
                polylines = _polyline_centres(model, solid.body, diagonal * _EDGE_CHORD)
            centre = polylines[edge.index]
            keys.append(centre[axis])
            widths.append(diagonal * _EDGE_MARGIN)
            continue
        keys.append(centre[axis])
        widths.append(0.0)
    return keys, widths


def _parallel(model: arris.Model, edges: Sequence[arris.Edge], axis: int) -> tuple[arris.Edge, ...]:
    """The line edges whose direction crosses `axis` within `CQ_TOLERANCE` (ADR-0020 rule 3).

    The direction is the line's ends' difference, normalised. A circle, an arc,
    an ellipse or a B-spline edge is never kept, as CadQuery's
    `ParallelDirSelector` keeps only `LINE` edges. A seam line is kept where it
    is parallel: a cylinder's seam is parallel to its axis wherever it lies.
    """
    unit = tuple(1.0 if i == axis else 0.0 for i in range(3))
    kept = []
    for edge in edges:
        c = model.curve(edge)
        if c.kind != "line":
            continue
        along = _sub(c.end, c.start)
        length = _length(along)
        if length == 0.0:
            continue
        if _length(_cross(unit, [a / length for a in along])) < CQ_TOLERANCE:
            kept.append(edge)
    return tuple(kept)


def select_edges(
    solid: arris.build.Solid,
    edges: Sequence[arris.Edge],
    selector: str | None,
    seams: Sequence[Seam] | None = None,
    *,
    fragments: frozenset[int] = frozenset(),
) -> tuple[arris.Edge, ...]:
    """The `edges` of `solid` that CadQuery's `selector` keeps (ADR-0020).

    `edges` are candidates from `edges_of_solid` or `edges_of_faces` (or edges
    a selector kept before); with no `selector` they are all kept. `selector`
    is one of `SELECTORS`. An axis selector (`AXIS_SELECTORS`) keeps the edges
    whose centre of mass lies furthest along (`>`) or least along (`<`) the
    axis, every one within CadQuery's `1e-4` of the first of its cluster, in
    ascending key (rule 2). `|X`, `|Y` and `|Z` keep the line edges parallel
    to the axis, in candidate order (rule 3). `'>Z or <Z'` keeps the edges
    either side keeps, each once, in candidate order (rule 4). Raises
    `UnsupportedApi` where the selection depends on a key arris does not give
    as CadQuery's kernel does: a seam on a face about another axis that
    `seams`, the chain's records of where Open CASCADE puts its seams, do not
    place (`None`: no seam of the chain is placed), or an ellipse arc or
    B-spline edge in the kept cluster or able to reach it. Also refuses a
    selection that depends on joining fragments of a unified face's boundary.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> candidates = edges_of_solid(box)
    >>> len(select_edges(box, candidates, ">Z")), len(select_edges(box, candidates, "|Z"))
    (4, 4)
    """
    if selector in OR_SELECTORS:
        both = {
            edge.index
            for side in selector.split(" or ")
            for edge in select_edges(solid, edges, side, seams, fragments=fragments)
        }
        return tuple(e for e in edges if e.index in both)
    if selector is None:
        selected = tuple(edges)
    elif selector in PARALLEL_SELECTORS:
        selected = _parallel(solid.model, edges, _AXIS[selector[1]])
    else:
        maximum = selector[0] == ">"
        keys, widths = _edge_keys(solid, edges, _AXIS[selector[1]], seams)
        fragment_slots = [i for i, edge in enumerate(edges) if edge.index in fragments]
        if fragment_slots:
            # A joined edge's key is a length-weighted mean of its fragment
            # keys. Enclose every possible mean, including the unjoined keys.
            lo = min(keys[i] - widths[i] for i in fragment_slots)
            hi = max(keys[i] + widths[i] for i in fragment_slots)
            mid = lo + (hi - lo) / 2
            for i in fragment_slots:
                keys[i], widths[i] = mid, max(mid - lo, hi - mid)
        kept = _pick_widths(keys, widths, maximum) if any(widths) else _pick(keys, maximum)
        if kept is None and fragment_slots:
            raise UnsupportedApi(f"Workplane.edges({selector!r}) on a split unified face boundary")
        if kept is None or any(widths[k] for k in kept if edges[k].index not in fragments):
            raise UnsupportedApi(
                f"Workplane.edges({selector!r}): the selection depends on an edge's place, "
                "which arris does not decide as CadQuery's kernel does"
            )
        selected = tuple(edges[k] for k in _ordered(kept, keys))
    if any(edge.index in fragments for edge in selected):
        raise UnsupportedApi(f"Workplane.edges({selector!r}) on a split unified face boundary")
    return selected


def plane_on(
    group: _FaceGroup, parent: arris.build.Workplane, model: arris.Model
) -> arris.build.Workplane:
    """The workplane CadQuery builds on one unified face (ADR-0017 and ADR-0022).

    Its origin is the parent origin projected onto the plane through the face's
    centre. Its normal is outward, taken at the centre's foot for curved
    faces. A singular foot raises RuntimeError. Unsupported surfaces and
    poorly conditioned feet raise UnsupportedApi.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> [top] = select_faces(box, ">Z")
    >>> plane_on(top, arris.build.Workplane.XY(), box.model).origin
    (0.0, 0.0, 6.0)
    """
    face = group[0]
    info = model.surface(face)
    origin = parent.origin
    if info.kind == "plane" and info.normal is not None and info.origin is not None:
        return _projected_plane(info.normal, origin, _dot(_sub(origin, info.origin), info.normal))
    if info.kind not in ("cylinder", "cone", "sphere", "torus"):
        raise UnsupportedApi(f"Workplane.workplane on a {info.kind} face")
    area, centre = _group_properties(model, group)
    n = _curved_normal(info, centre, math.sqrt(area))
    if face.reversed:
        n = (-n[0], -n[1], -n[2])
    return _projected_plane(n, origin, _dot(_sub(origin, centre), n))


def _foot_direction(vector: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    distance = _length(vector)
    if distance <= _CENTRE_ERROR * scale:
        raise RuntimeError(_NO_FOOT)
    if distance <= _FOOT_MIN * scale:
        # See unsupported-faces-workplane-foot-band.
        raise UnsupportedApi("Workplane.workplane on a curved face with an unstable foot")
    return (vector[0] / distance, vector[1] / distance, vector[2] / distance)


def _curved_normal(
    info: arris.SurfaceInfo, centre: tuple[float, float, float], scale: float
) -> tuple[float, float, float]:
    """The untrimmed surface's normal at the centre's nearest point."""
    assert info.origin is not None
    delta = _sub(centre, info.origin)
    if info.kind == "sphere":
        return _foot_direction(delta, scale)
    axis = info.axis
    assert axis is not None
    height = _dot(delta, axis)
    radial = _foot_direction(_sub(delta, tuple(height * v for v in axis)), scale)
    if info.kind == "cone":
        assert info.half_angle is not None
        cosine, sine = math.cos(info.half_angle), math.sin(info.half_angle)
        # The arris cone widens along its axis, so its normal tilts back.
        return (
            cosine * radial[0] - sine * axis[0],
            cosine * radial[1] - sine * axis[1],
            cosine * radial[2] - sine * axis[2],
        )
    if info.kind == "torus":
        assert info.major_radius is not None
        return _foot_direction(_sub(delta, tuple(info.major_radius * v for v in radial)), scale)
    return radial


def _projected_plane(
    n: Sequence[float], origin: Sequence[float], height: float
) -> arris.build.Workplane:
    across = _cross((0.0, 0.0, 1.0), n)
    length = _length(across)
    at = (
        origin[0] - n[0] * height,
        origin[1] - n[1] * height,
        origin[2] - n[2] * height,
    )
    if 0.0 < length < CQ_TOLERANCE:
        # CadQuery's geometry transform squares the fallback x to the normal.
        return arris.build.Workplane.of(at, n, x_axis=(1.0, 0.0, 0.0))
    x = (
        (1.0, 0.0, 0.0)
        if length == 0.0
        else (across[0] / length, across[1] / length, across[2] / length)
    )
    y = _cross(n, x)
    return arris.build.Workplane(at, x, y, (n[0], n[1], n[2]))


# CadQuery 2.3.0's `DirectionMinMaxSelector.filter` on an empty list, which `faces`
# hands it when no object on the stack has a face: raised as `ValueError`.
NO_FACES = "Can not return the Nth element of an empty list"
# Open CASCADE's `Standard_Failure` that CadQuery 2.3.0's `fillet` and `chamfer` raise when
# every edge they are given is a seam (ADR-0020 rule 5), raised here as `ValueError`.
NO_SUITABLE_EDGES = "Standard_Failure: There are no suitable edges for chamfer or fillet"
# CadQuery 2.3.0's `Workplane.workplane` on several objects: its words, raised
# as `ValueError` (ADR-0017 rule 4).
NOT_PLANAR = "If multiple objects selected, they all must be planar faces."
NOT_COPLANAR = "Selected faces must be co-planar."


def _cone_apex(info: arris.SurfaceInfo) -> tuple[float, float, float]:
    """The apex from the reference circle of arris's cone."""
    origin, axis, radius, angle = info.origin, info.axis, info.radius, info.half_angle
    assert origin is not None
    assert axis is not None
    assert radius is not None
    assert angle is not None
    # The radius increases along the axis, so the apex is behind the reference circle.
    height = -radius / math.tan(angle)
    return (
        origin[0] + axis[0] * height,
        origin[1] + axis[1] * height,
        origin[2] + axis[2] * height,
    )


def _same_surface(
    a: arris.SurfaceInfo, b: arris.SurfaceInfo, same_sense: bool, model: arris.Model
) -> bool:
    """Whether adjacent faces have one oriented analytic surface (ADR-0022 rule 2)."""
    if a.kind != b.kind or a.origin is None or b.origin is None:
        return False
    tolerance, angular = model.tolerance, model.angular_tolerance
    delta = _sub(a.origin, b.origin)
    if a.kind == "plane":
        n, m = a.normal, b.normal
        return (
            n is not None
            and m is not None
            and _dot(n, m) > 0.0
            and _length(_cross(n, m)) <= angular
            and max(abs(_dot(delta, n)), abs(_dot(delta, m))) <= tolerance
        )
    if not same_sense:
        return False
    if a.kind == "sphere":
        assert a.radius is not None
        assert b.radius is not None
        return _length(delta) <= tolerance and abs(a.radius - b.radius) <= tolerance
    u, v = a.axis, b.axis
    if u is None or v is None or _length(_cross(u, v)) > angular:
        return False
    if a.kind == "cone":
        assert a.half_angle is not None
        assert b.half_angle is not None
        return (
            _dot(u, v) > 0.0
            and abs(a.half_angle - b.half_angle) <= angular
            and _length(_sub(_cone_apex(a), _cone_apex(b))) <= tolerance
        )
    if a.kind == "torus":
        assert a.major_radius is not None
        assert b.major_radius is not None
        assert a.minor_radius is not None
        assert b.minor_radius is not None
        return (
            _length(delta) <= tolerance
            and abs(a.major_radius - b.major_radius) <= tolerance
            and abs(a.minor_radius - b.minor_radius) <= tolerance
        )
    if a.kind == "cylinder":
        assert a.radius is not None
        assert b.radius is not None
        return (
            abs(a.radius - b.radius) <= tolerance
            and max(_length(_cross(delta, u)), _length(_cross(delta, v))) <= tolerance
        )
    return False


def _normals_tie(n0: Sequence[float], n1: Sequence[float]) -> bool:
    """CadQuery's `_isCoPlanar` normal test: any one component within `CQ_TOLERANCE`."""
    return any(abs(n0[k] - n1[k]) < CQ_TOLERANCE for k in range(3))


def plane_on_faces(
    groups: Sequence[_FaceGroup], parent: arris.build.Workplane, model: arris.Model
) -> arris.build.Workplane:
    """The workplane CadQuery's `workplane()` builds on the faces a selector kept (ADR-0017).

    One unified face uses its plane or the plane through its centre at the
    normal of its foot (ADR-0022 rule 4). For several faces, if any is curved,
    raise CadQuery's `ValueError` (`NOT_PLANAR`). Co-planar faces with a
    common outward normal place the plane at their area-weighted offset
    (ADR-0022 rule 3). If all face orders fail CadQuery's signed centre test,
    raise its `ValueError` (`NOT_COPLANAR`). An order-dependent or uncertain
    result raises `UnsupportedApi`.

    >>> import arris.build
    >>> slab = arris.build.Solid.box((0, 0, 0), (10, 10, 2))
    >>> part = slab.cut(arris.build.Solid.box((4, -1, 0), (6, 11, 4)))
    >>> tops = select_faces(part, ">Z")
    >>> len(tops), plane_on_faces(tops, arris.build.Workplane.XY(), part.model).origin
    (2, (0.0, 0.0, 2.0))
    """
    if len(groups) == 1:
        return plane_on(groups[0], parent, model)
    infos = [model.surface(group[0]) for group in groups]
    if any(info.kind != "plane" for info in infos):
        raise ValueError(NOT_PLANAR)
    normals: list[tuple[float, float, float]] = []
    origins: list[tuple[float, float, float]] = []
    for info in infos:
        if info.normal is None or info.origin is None:
            raise UnsupportedApi("Workplane.workplane on a plane without a frame")
        normals.append(info.normal)
        origins.append(info.origin)
    n0 = normals[0]
    pairs = list(itertools.permutations(range(len(normals)), 2))
    common_normal = all(
        _length(_cross(normals[i], normals[j])) <= model.angular_tolerance
        and _dot(normals[i], normals[j]) > 0.0
        for i, j in pairs
    )
    areas, centres = zip(*(_group_properties(model, group) for group in groups), strict=True)
    widths = [_CENTRE_ERROR * math.sqrt(area) for area in areas]

    def coplanar(i: int, j: int) -> bool | None:
        n, other = normals[i], normals[j]
        if not _normals_tie(n, other):
            return False
        if _dot(n, other) < 0 and _length(_cross(n, other)) <= model.angular_tolerance:
            return None  # Opposite normals depend on CadQuery's face order.
        # For faces with the same axial normal, the plane offsets give
        # the signed centre distance without quadrature.
        if n == other and sum(v == 0.0 for v in n) == 2:
            separation = _dot(n, _sub(origins[i], origins[j]))
            reach = _FLOAT_SLACK
        else:
            separation = _dot(n, _sub(centres[i], centres[j]))
            reach = sum(abs(v) for v in n) * (widths[i] + widths[j]) + _FLOAT_SLACK
        if separation - reach >= CQ_TOLERANCE:
            return False
        if separation + reach < CQ_TOLERANCE:
            return True
        return None

    # CadQuery tests each face against the first. Across possible orders,
    # every directed pair must pass, or every first face must see a failure.
    checks = [coplanar(i, j) for i, j in pairs]
    if common_normal and all(check is True for check in checks):
        heights = [
            _dot(_sub(parent.origin, origin if n == n0 else centre), n0)
            for origin, n, centre in zip(origins, normals, centres, strict=True)
        ]
        base = min(heights)
        shift = math.fsum(a * (h - base) for a, h in zip(areas, heights, strict=True))
        height = base + shift / math.fsum(areas)
        return _projected_plane(n0, parent.origin, height)
    if len({i for (i, _), check in zip(pairs, checks, strict=True) if check is False}) == len(
        normals
    ):
        raise ValueError(NOT_COPLANAR)
    raise UnsupportedApi("Workplane.workplane on faces whose co-planarity needs their centres")
