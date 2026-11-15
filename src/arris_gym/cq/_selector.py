"""CadQuery's axis selectors over arris: which faces `faces(">Z")` keeps, and the plane on them.

ADR-0017, and ADR-0020 for edges. Private: `Workplane.faces`, `Workplane.workplane`,
`Workplane.edges`, `Workplane.fillet` and `Workplane.chamfer` call it.
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
    "SELECTORS",
    "Edges",
    "Faces",
    "edges_of_faces",
    "edges_of_solid",
    "plane_on",
    "plane_on_faces",
    "select_edges",
    "select_faces",
]

# The axis selectors the subset admits: `DirectionMinMaxSelector` on one world
# axis, `>` the furthest cluster and `<` the nearest (ADR-0017).
AXIS_SELECTORS = (">X", "<X", ">Y", "<Y", ">Z", "<Z")
SELECTORS = AXIS_SELECTORS
_AXIS = {"X": 0, "Y": 1, "Z": 2}

# CadQuery 2.3.0's default tolerance for `DirectionMinMaxSelector`, for
# `Workplane._computeXdir` and for `_isCoPlanar`: faces whose keys lie within it
# of a cluster's first key tie, and a normal shorter than it is no direction.
# ADR-0017 rule 1. In model units.
CQ_TOLERANCE = 1e-4
# `_pick` compares keys after summing and subtracting them in floats, so a
# difference worked out one way can fall a few ulps (of keys under 1) on the
# other side of `CQ_TOLERANCE` from the same difference worked out another.
# `_pick_within` keeps this much clear of that edge: a selection within it is
# refused, as one the margin could change. In model units.
_FLOAT_SLACK = 1e-12
# The chord a face's tessellation is cut at when its centre is estimated, as a
# fraction of the solid's box diagonal (ADR-0017 rule 2). The estimate's error
# is about 0.4 chords.
_ESTIMATE_CHORD = 1e-5
# How far an estimated key is trusted, as a fraction of the same diagonal:
# ten chords, 25 times the error measured on a half cylinder (ADR-0017 rule 2).
_ESTIMATE_MARGIN = 1e-4


@dataclass(frozen=True)
class Faces:
    """The faces a selector kept, on a stack: the solid they belong to and the faces.

    The faces are in CadQuery's order, ascending by their key along the
    selector's axis, a tie in the kernel's face order.
    """

    solid: arris.build.Solid
    faces: tuple[arris.Face, ...]


@dataclass(frozen=True)
class Edges:
    """The edges a selector kept, on a stack: the solid they belong to and the edges.

    The edges are the solid's own `arris.Edge` values, in CadQuery's order:
    ascending by their key along the selector's axis, a tie in the kernel's
    edge order. Only `edges`, `fillet` and `chamfer` read it (ADR-0020 rule 6).
    """

    solid: arris.build.Solid
    edges: tuple[arris.Edge, ...]


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


def _pick_within(
    keys: Sequence[float], estimated: Sequence[bool], margin: float, maximum: bool
) -> list[int] | None:
    """`_pick_widths` with every estimated key `margin` wide and every other exact."""
    return _pick_widths(keys, [margin if e else 0.0 for e in estimated], maximum)


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


def _estimates(
    model: arris.Model, body: arris.Body, faces: Sequence[arris.Face], axis: int, chord: float
) -> list[float]:
    """The area centroid of each face's tessellation along `axis`, in `faces` order.

    Summed in triangle order in Python floats, so it has the same bits on
    every machine (ADR-0017 rule 2). Raises `UnsupportedApi` for a face
    without area in the mesh.
    """
    mesh = model.tessellate_faces(body, faces, chord)
    points = struct.unpack(f"<{3 * mesh.n_positions}d", mesh.positions)
    corners = struct.unpack(f"<{3 * mesh.n_triangles}I", mesh.triangles)
    runs = {face: (first, end) for face, first, end in mesh.faces}
    found: list[float] = []
    for face in faces:
        first, end = runs[face]
        weighted = 0.0
        area = 0.0
        for t in range(first, end):
            a, b, c = (
                points[3 * corners[3 * t + k] : 3 * corners[3 * t + k] + 3] for k in range(3)
            )
            ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            twice = _length(_cross(ab, ac))
            weighted += twice * (a[axis] + b[axis] + c[axis]) / 3.0
            area += twice
        if area == 0.0:
            raise UnsupportedApi(f"Workplane.faces: a face with no area in its mesh ({face!r})")
        found.append(weighted / area)
    return found


def select_faces(
    solid: arris.build.Solid, selector: str, among: Sequence[arris.Face] | None = None
) -> tuple[arris.Face, ...]:
    """The faces of `solid`, or of `among` them, that CadQuery's `selector` keeps (ADR-0017).

    `among` are faces of `solid` a selector kept before (a `faces` on a stack
    of faces, ADR-0018 rule 5): CadQuery ranks those only. The solid still
    gives the part's box, the scale of the margin.

    `selector` is one of `AXIS_SELECTORS`. A face's key is its centre of mass
    along the axis: its plane's offset where it is a plane normal to the axis
    (exact), else known from its box where that settles the selection, else
    the area centroid of its tessellation, trusted at a margin. Raises
    `UnsupportedApi` where moving an estimated key by that margin could change
    the selection: it then depends on a centre arris does not give.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> [box.model.surface(f).origin for f in select_faces(box, ">Z")]
    [(0.0, 0.0, 6.0)]
    """
    maximum = selector[0] == ">"
    axis = _AXIS[selector[1]]
    unit = tuple(1.0 if i == axis else 0.0 for i in range(3))
    model = solid.model
    faces = list(model.faces(solid.body) if among is None else among)
    exact: dict[int, float] = {}
    loose: list[int] = []
    for i, face in enumerate(faces):
        info = model.surface(face)
        if (
            info.kind == "plane"
            and info.normal is not None
            and info.origin is not None
            and _length(_cross(info.normal, unit)) <= model.angular_tolerance
        ):
            exact[i] = info.origin[axis]
        else:
            loose.append(i)
    # A loose face's box says where its key can lie. One the exact keys put
    # out of reach of the cluster, by more than the tolerance, is left out.
    exact_keys = sorted(exact.values())
    start = _last_start(exact_keys) if exact_keys else 0.0
    below = [k for k in exact_keys if k < start]
    # The last cluster's start holds against a key below it only past a gap.
    gap = not below or below[-1] < start - CQ_TOLERANCE
    undecided: list[int] = []
    for i in loose:
        box = model.bounds(faces[i])
        if box is None or not exact_keys:
            undecided.append(i)
        elif maximum:
            if not (gap and box[1][axis] < start - CQ_TOLERANCE):
                undecided.append(i)
        elif not box[0][axis] > exact_keys[0] + CQ_TOLERANCE:
            undecided.append(i)
    if not undecided:
        keys = list(exact.values())
        order = list(exact)
        return tuple(faces[order[k]] for k in _ordered(_pick(keys, maximum), keys))
    whole = model.bounds(solid.body)
    if whole is None:
        raise UnsupportedApi("Workplane.faces on a solid without a box")
    diagonal = _length([whole[1][k] - whole[0][k] for k in range(3)])
    values = _estimates(
        model, solid.body, [faces[i] for i in undecided], axis, diagonal * _ESTIMATE_CHORD
    )
    order = [*exact, *undecided]
    keys = [*exact.values(), *values]
    margin = diagonal * _ESTIMATE_MARGIN
    kept = _pick_within(keys, [i >= len(exact) for i in range(len(keys))], margin, maximum)
    if kept is None:
        raise UnsupportedApi(_depends(selector))
    return tuple(faces[order[k]] for k in _ordered(kept, keys))


def _ordered(kept: Sequence[int], keys: Sequence[float]) -> list[int]:
    """`kept` in ascending key, a tie in the order given."""
    return sorted(kept, key=lambda k: keys[k])


def _last_start(sorted_keys: Sequence[float]) -> float:
    """The first key of the last greedy cluster of `sorted_keys`."""
    start = sorted_keys[0]
    for key in sorted_keys:
        if key - start > CQ_TOLERANCE:
            start = key
    return start


def _depends(selector: str) -> str:
    return (
        f"Workplane.faces({selector!r}): the selection depends on the centre of a face "
        "that arris does not give"
    )


# --- edges (ADR-0020) -------------------------------------------------------


def edges_of_solid(solid: arris.build.Solid) -> tuple[arris.Edge, ...]:
    """The candidate edges of `solid`, in the kernel's order (ADR-0020 rule 1).

    A `degenerate` edge is left out, as CadQuery's `Edges()` leaves out a
    degenerated edge (a sphere's pole).
    """
    model = solid.model
    return tuple(e for e in model.edges(solid.body) if model.curve(e).kind != "degenerate")


def edges_of_faces(solid: arris.build.Solid, faces: Sequence[arris.Face]) -> tuple[arris.Edge, ...]:
    """The candidate edges of `faces`: each edge once, in the order first found (ADR-0020 rule 1).

    Each is the solid's own edge value, so that an edge shared by two faces
    is one, and a reversed edge is read as the solid's body does.
    """
    model = solid.model
    own = {e.index: e for e in edges_of_solid(solid)}
    found: dict[int, arris.Edge] = {}
    for face in faces:
        for edge in model.edges_of(face):
            if edge.index in own and edge.index not in found:
                found[edge.index] = own[edge.index]
    return tuple(found.values())


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


def _edge_keys(
    solid: arris.build.Solid, edges: Sequence[arris.Edge], axis: int
) -> tuple[list[float], list[float]]:
    """Each edge's key along `axis` and how far it is trusted (ADR-0020 rule 2).

    A width of 0 is an exact key. A seam's key is exact where its face is a
    surface of revolution about an axis parallel to `axis`, else it lies
    anywhere on its face, so it is the face's box (centre, half the extent).
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
                box = model.bounds(faces[0])
                if box is None:
                    raise UnsupportedApi("Workplane.edges on a seam of a face without a box")
                keys.append((box[0][axis] + box[1][axis]) / 2.0)
                widths.append((box[1][axis] - box[0][axis]) / 2.0)
                continue
        if centre is None:
            if polylines is None:
                polylines = _polyline_centres(model, solid.body, diagonal * _ESTIMATE_CHORD)
            centre = polylines[edge.index]
            keys.append(centre[axis])
            widths.append(diagonal * _ESTIMATE_MARGIN)
            continue
        keys.append(centre[axis])
        widths.append(0.0)
    return keys, widths


def select_edges(
    solid: arris.build.Solid, edges: Sequence[arris.Edge], selector: str | None
) -> tuple[arris.Edge, ...]:
    """The `edges` of `solid` that CadQuery's `selector` keeps (ADR-0020).

    `edges` are candidates from `edges_of_solid` or `edges_of_faces` (or edges
    a selector kept before); with no `selector` they are all kept. `selector`
    is one of `SELECTORS`' six axis selectors: the edges whose centre of mass
    lies furthest along (`>`) or least along (`<`) the axis, every one within
    CadQuery's `1e-4` of the first of its cluster, in ascending key. Raises
    `UnsupportedApi` where the selection depends on a key arris does not give
    as CadQuery's kernel does: a seam on a face about another axis, or an
    ellipse arc or B-spline edge in the kept cluster or able to reach it.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> len(select_edges(box, edges_of_solid(box), ">Z"))
    4
    """
    if selector is None:
        return tuple(edges)
    maximum = selector[0] == ">"
    keys, widths = _edge_keys(solid, edges, _AXIS[selector[1]])
    kept = _pick_widths(keys, widths, maximum) if any(widths) else _pick(keys, maximum)
    if kept is None or any(widths[k] for k in kept):
        raise UnsupportedApi(
            f"Workplane.edges({selector!r}): the selection depends on an edge's place, "
            "which arris does not decide as CadQuery's kernel does"
        )
    return tuple(edges[k] for k in _ordered(kept, keys))


def plane_on(
    face: arris.Face, parent: arris.build.Workplane, model: arris.Model
) -> arris.build.Workplane:
    """The workplane CadQuery's `workplane()` builds on one planar `face` (ADR-0017 rule 3).

    Its normal is the face's outward normal, its x is `(0, 0, 1)` crossed with
    the normal and normalised, or +x when that is shorter than `CQ_TOLERANCE`,
    and its origin is `parent`'s origin projected onto the face's plane.
    Raises `UnsupportedApi` for a face that is not a plane.

    >>> import arris.build
    >>> box = arris.build.Solid.box((0, 0, 0), (2, 4, 6))
    >>> top = select_faces(box, ">Z")[0]
    >>> plane_on(top, arris.build.Workplane.XY(), box.model).origin
    (0.0, 0.0, 6.0)
    """
    info = model.surface(face)
    if info.kind != "plane" or info.normal is None or info.origin is None:
        raise UnsupportedApi(f"Workplane.workplane on a {info.kind} face")
    n = info.normal
    across = _cross((0.0, 0.0, 1.0), n)
    length = _length(across)
    x = (
        (1.0, 0.0, 0.0)
        if length < CQ_TOLERANCE
        else (across[0] / length, across[1] / length, across[2] / length)
    )
    y = _cross(n, x)
    o, f = parent.origin, info.origin
    height = (o[0] - f[0]) * n[0] + (o[1] - f[1]) * n[1] + (o[2] - f[2]) * n[2]
    at = (o[0] - n[0] * height, o[1] - n[1] * height, o[2] - n[2] * height)
    return arris.build.Workplane(at, x, y, (n[0], n[1], n[2]))


# CadQuery 2.3.0's `DirectionMinMaxSelector.filter` on an empty list, which `faces`
# hands it when no object on the stack has a face: raised as `ValueError`.
NO_FACES = "Can not return the Nth element of an empty list"
# CadQuery 2.3.0's `Workplane.workplane` on several objects: its words, raised
# as `ValueError` (ADR-0017 rule 4).
NOT_PLANAR = "If multiple objects selected, they all must be planar faces."
NOT_COPLANAR = "Selected faces must be co-planar."
# The parameters two curved surfaces of one kind share when they are one surface.
_SHAPE = ("radius", "major_radius", "minor_radius", "half_angle")


def _surely_apart(a: arris.SurfaceInfo, b: arris.SurfaceInfo, model: arris.Model) -> bool:
    """Whether two curved surfaces are certainly not one: another kind, or another size.

    Surfaces of one kind and one size may be one surface the kernels split
    differently, so they are never called apart (ADR-0017 rule 5).
    """
    if a.kind != b.kind:
        return True
    for name in _SHAPE:
        p, q = getattr(a, name), getattr(b, name)
        within = model.angular_tolerance if name == "half_angle" else model.tolerance
        if p is not None and q is not None and abs(p - q) > within:
            return True
    return False


def _normals_tie(n0: Sequence[float], n1: Sequence[float]) -> bool:
    """CadQuery's `_isCoPlanar` normal test: any one component within `CQ_TOLERANCE`."""
    return any(abs(n0[k] - n1[k]) < CQ_TOLERANCE for k in range(3))


def plane_on_faces(
    faces: Sequence[arris.Face], parent: arris.build.Workplane, model: arris.Model
) -> arris.build.Workplane:
    """The workplane CadQuery's `workplane()` builds on the faces a selector kept (ADR-0017).

    One face is `plane_on`'s. Several (rule 4): faces that are not all planar
    raise CadQuery's `ValueError` (`NOT_PLANAR`), unless all lie on curved
    surfaces of one kind and size, which may be one face to Open CASCADE and
    are `UnsupportedApi` (rule 5). Planar faces with one outward normal and
    one offset, within the model's tolerances, give that plane, whatever the
    face order. Planar faces at offsets apart need their areas, opposite
    normals and other normals their centres or CadQuery's face order, so
    they are `UnsupportedApi`, except where every face's normal fails
    CadQuery's co-planar normal test against another face, whichever comes
    first: that raises its `ValueError` (`NOT_COPLANAR`).

    >>> import arris.build
    >>> slab = arris.build.Solid.box((0, 0, 0), (10, 10, 2))
    >>> part = slab.cut(arris.build.Solid.box((4, -1, 0), (6, 11, 4)))
    >>> tops = select_faces(part, ">Z")
    >>> len(tops), plane_on_faces(tops, arris.build.Workplane.XY(), part.model).origin
    (2, (0.0, 0.0, 2.0))
    """
    if len(faces) == 1:
        return plane_on(faces[0], parent, model)
    infos = [model.surface(face) for face in faces]
    curved = [info for info in infos if info.kind != "plane"]
    if curved:
        if len(curved) == len(infos) and not any(
            _surely_apart(curved[0], other, model) for other in curved[1:]
        ):
            raise UnsupportedApi(f"Workplane.workplane on a {curved[0].kind} face")
        raise ValueError(NOT_PLANAR)
    normals: list[tuple[float, float, float]] = []
    offsets: list[float] = []
    for info in infos:
        if info.normal is None or info.origin is None:
            raise UnsupportedApi("Workplane.workplane on a plane without a frame")
        n, o = info.normal, info.origin
        normals.append((n[0], n[1], n[2]))
        offsets.append(o[0] * n[0] + o[1] * n[1] + o[2] * n[2])
    n0 = normals[0]
    if all(
        _length(_cross(n0, n)) <= model.angular_tolerance
        and n0[0] * n[0] + n0[1] * n[1] + n0[2] * n[2] > 0.0
        for n in normals[1:]
    ):
        if all(abs(offset - offsets[0]) <= model.tolerance for offset in offsets[1:]):
            return plane_on(faces[0], parent, model)
        raise UnsupportedApi("Workplane.workplane on parallel faces at different offsets")
    # CadQuery tests each face against its first, an order the kernels do not
    # share: its error is certain only when it holds for every first face.
    if all(
        any(not _normals_tie(normals[i], normals[j]) for j in range(len(normals)) if j != i)
        for i in range(len(normals))
    ):
        raise ValueError(NOT_COPLANAR)
    raise UnsupportedApi("Workplane.workplane on faces whose co-planarity needs their centres")
