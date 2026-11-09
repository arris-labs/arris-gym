"""The field's metrics: BenchCAD's voxel IoU on a 64³ grid and its Chamfer distance times 1000.

docs/ARCHITECTURE.md §The reward. Computed as BenchCAD's own scorer computes
them, so a number here compares with a published one; read (MIT) at
`BenchCAD/BenchCAD-main@77fd16a8`: `benchcad_core/scoring/iou.py`
(`iou_step_vs_step`, `_load_normalized_mesh`, `_vox_dense`) and
`Vision2Code/scoring/composite_metrics.py` (`compute_chamfer`). Their
voxels come from trimesh 4.12.2 (MIT), `Trimesh.voxelized` and
`VoxelGrid.fill`, whose steps are reimplemented here on numpy alone:
`voxel/creation.py` (`voxelize_subdivide`), `remesh.py` (`subdivide`,
`subdivide_to_size`), `voxel/morphology.py` (`fill_holes`, which is
`scipy.ndimage.binary_fill_holes` at its documented default, faces-only
connectivity). `PROVENANCE.md` names them.

Each body is tessellated at an absolute chord of 0.05 (their
`tessellate(0.05)`), normalised to its own mesh's box (centre at 0.5,
longest side 1), subdivided until no edge exceeds half a voxel, each
vertex rounded to its voxel, the shell's holes filled, and the occupied box
centred in a 68³ grid. The voxel IoU counts both grids' cells. Chamfer is
the mean squared nearest distance both ways between 2,048 surface samples
of each normalised mesh, times 1000. Two differences from theirs, by
design: our mesh is the kernel's, not Open CASCADE's, and our samples come
from `PCG64(seed)` where theirs are unseeded, so a body against itself has
a Chamfer of exactly 0. Both metrics are scale-blind: a cube against its
double gives 1 and 0. Every operation is one IEEE 754 rounds exactly or
one that does not round (§Determinism). Private: called in-process on
bodies already read into a fresh model, which only a worker does.
"""

from __future__ import annotations

import math

import arris
import numpy as np
import numpy.typing as npt

from arris_gym.reward._iou import CHUNK_ELEMENTS
from arris_gym.reward._score import FieldMetrics
from arris_gym.reward._surface import nearest_squared, surface_samples

_Floats = npt.NDArray[np.float64]
_Grid = npt.NDArray[np.bool_]
_Mesh = tuple[_Floats, _Floats, _Floats]

# BenchCAD's tessellation: `solid.tessellate(0.05)`, an absolute chord in
# the part's own units (millimetres in their corpus).
TESSELLATION_CHORD = 0.05
# Their grid: a pitch of 1/64 of the normalised longest side, the occupied
# box centred in a grid of 64 + 4 cells a side ("padded to 68³ to handle
# off-axis geometry").
GRID_RESOLUTION = 64
GRID_PADDING = 4
# trimesh's `voxelize_subdivide` defaults: subdivide until every edge is at
# most pitch / 2, and refuse a mesh still too coarse after 10 rounds. A
# normalised mesh's edges are at most √3, which 8 rounds bring under 1/128,
# so the cap is never met by a mesh of the kernel's.
EDGE_FACTOR = 2.0
MAX_SUBDIVISIONS = 10
# Their normalisation refuses a mesh whose longest side is below this
# ("degenerate geometry").
DEGENERATE_EXTENT = 1e-9
# Their Chamfer: 2,048 area-weighted samples per body, reported times 1000 here
# as the field reports it.
CHAMFER_SAMPLES = 2048
CHAMFER_SCALE = 1000.0
# Triangles subdivided at once: their corners and midpoints are a few dozen
# float64 arrays of this many rows, so memory stays bounded whatever the
# mesh. Not a tolerance: the voxels hit do not depend on it.
SUBDIVIDE_CHUNK = CHUNK_ELEMENTS
# Hit voxels are marked in a grid one cell wider than the normalised box on
# every side, since a vertex rounded at the box's edge lands on index 0 or
# GRID_RESOLUTION and rounding of the normalisation never moves it further.
_HIT_MARGIN = 1


def normalised_mesh(model: arris.Model, body: arris.Body) -> _Mesh:
    """Each triangle's corners of `body`'s mesh at `TESSELLATION_CHORD`, in its own unit box.

    The mesh's own vertices give the box: centre moved to 0.5, divided by
    the longest side, as BenchCAD's `_load_normalized_mesh` does. Raises the
    kernel's `ArrisError` where it cannot mesh the body, and `ValueError`
    for an empty mesh or one whose longest side is below `DEGENERATE_EXTENT`.
    """
    positions, triangles = model.tessellate(body, TESSELLATION_CHORD).to_numpy()
    vertices = np.asarray(positions, dtype=np.float64)
    faces = np.asarray(triangles, dtype=np.intp)
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError("the body's tessellation is empty")
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    centre = (low + high) / 2.0
    longest = float((high - low).max())
    if longest < DEGENERATE_EXTENT:
        raise ValueError("the body's mesh is degenerate: its longest side is below 1e-9")
    unit = (vertices - centre) / longest + 0.5
    corners = unit[faces]
    return corners[:, 0, :], corners[:, 1, :], corners[:, 2, :]


def _edge(p: _Floats, q: _Floats) -> _Floats:
    d = q - p
    return np.asarray(np.sqrt(d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1] + d[:, 2] * d[:, 2]))


def surface_voxels(mesh: _Mesh) -> _Grid:
    """The voxels the surface of a normalised mesh hits, as the box of them.

    trimesh's `voxelize_subdivide` at a pitch of 1/`GRID_RESOLUTION`: a
    triangle with an edge over pitch / `EDGE_FACTOR` is cut into four at its
    edges' midpoints, again until none is, and every corner of the triangles
    left is rounded (half to even) to its voxel. Each triangle is cut on its
    own, which hits the same corners as cutting the whole mesh at once, in
    chunks of `SUBDIVIDE_CHUNK`. The result spans the hit voxels' box, its
    first cell the lowest hit. Raises `ValueError` for a triangle still too
    long after `MAX_SUBDIVISIONS` rounds, as trimesh does.
    """
    pitch = 1.0 / GRID_RESOLUTION
    max_edge = pitch / EDGE_FACTOR
    side = GRID_RESOLUTION + 1 + 2 * _HIT_MARGIN
    hits = np.zeros((side, side, side), dtype=np.bool_)
    work: list[tuple[_Floats, _Floats, _Floats, int]] = [(*mesh, 0)]
    while work:
        a, b, c, depth = work.pop()
        if len(a) > SUBDIVIDE_CHUNK:
            half = len(a) // 2
            work.append((a[half:], b[half:], c[half:], depth))
            work.append((a[:half], b[:half], c[:half], depth))
            continue
        too_long = (_edge(a, b) > max_edge) | (_edge(b, c) > max_edge) | (_edge(c, a) > max_edge)
        done = ~too_long
        corners = np.concatenate((a[done], b[done], c[done]))
        index = np.rint(corners / pitch).astype(np.int64) + _HIT_MARGIN
        if len(index) and (index.min() < 0 or index.max() >= side):
            raise ValueError("a vertex of the normalised mesh lies outside its unit box")
        hits[index[:, 0], index[:, 1], index[:, 2]] = True
        if not too_long.any():
            continue
        if depth >= MAX_SUBDIVISIONS:
            raise ValueError("max_iter exceeded!")  # trimesh's own words
        a, b, c = a[too_long], b[too_long], c[too_long]
        ab, bc, ca = (a + b) / 2.0, (b + c) / 2.0, (c + a) / 2.0
        work.append(
            (
                np.concatenate((a, ab, ca, ab)),
                np.concatenate((ab, b, bc, bc)),
                np.concatenate((ca, bc, c, ca)),
                depth + 1,
            )
        )
    occupied = np.nonzero(hits)
    if len(occupied[0]) == 0:
        raise ValueError("the mesh hits no voxel")
    low = [int(axis.min()) for axis in occupied]
    high = [int(axis.max()) + 1 for axis in occupied]
    return np.asarray(hits[low[0] : high[0], low[1] : high[1], low[2] : high[2]])


def _along(reached: _Grid, empty: _Grid, axis: int) -> _Grid:
    """`reached` spread through every run of `empty` cells along `axis` it touches."""
    e = np.moveaxis(empty, axis, -1)
    r = np.moveaxis(reached, axis, -1)
    length = e.shape[-1]
    lines = e.reshape(-1, length)
    # A run's id: the line's number and the count of full cells before it.
    run = np.cumsum(~lines, axis=1) + (np.arange(len(lines)) * (length + 1))[:, None]
    touched = np.zeros(len(lines) * (length + 1), dtype=np.bool_)
    touched[run[r.reshape(-1, length)]] = True
    spread = (touched[run] & lines).reshape(e.shape)
    return np.asarray(np.moveaxis(spread, -1, axis))


def fill_holes(shell: _Grid) -> _Grid:
    """`shell` with every empty cell the outside cannot reach filled.

    `scipy.ndimage.binary_fill_holes` at its default structure, as trimesh's
    `fill` calls it: an empty cell is outside when a path of empty cells,
    each step across a face, joins it to the grid's border. Found by
    spreading from the border's empty cells along each axis in turn until
    nothing changes; integer and boolean operations only.
    """
    empty = ~shell
    border = np.zeros_like(shell)
    border[0, :, :] = border[-1, :, :] = True
    border[:, 0, :] = border[:, -1, :] = True
    border[:, :, 0] = border[:, :, -1] = True
    outside = empty & border
    while True:
        before = outside
        for axis in range(3):
            outside = _along(outside, empty, axis)
        if np.array_equal(outside, before):
            return np.asarray(~outside)


def centred(grid: _Grid, size: int) -> _Grid:
    """`grid` in a `size`³ grid, offset by half the shapes' difference (floored), cut to fit.

    BenchCAD's `_vox_dense`: the grid's own position is dropped, so each
    body is centred by its voxel box alone.
    """
    out = np.zeros((size, size, size), dtype=np.bool_)
    shape = np.array(grid.shape)
    start = np.clip((size - shape) // 2, 0, None)
    stop = np.clip(start + shape, None, size)
    span = stop - start
    out[start[0] : stop[0], start[1] : stop[1], start[2] : stop[2]] = grid[
        : span[0], : span[1], : span[2]
    ]
    return out


def voxel_grid(mesh: _Mesh) -> _Grid:
    """The filled voxels of a normalised mesh, centred in the field's 68³ grid."""
    return centred(fill_holes(surface_voxels(mesh)), GRID_RESOLUTION + GRID_PADDING)


def voxel_iou(a: _Grid, b: _Grid) -> float:
    """Cells in both grids over cells in either; 0 when neither has one, as BenchCAD's is."""
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 0.0
    return int(np.count_nonzero(a & b)) / union


def chamfer(a: _Mesh, b: _Mesh, *, seed: int) -> float:
    """The mean squared nearest distance from `a`'s samples to `b`'s plus the reverse.

    `CHAMFER_SAMPLES` samples per mesh by area from a fresh `PCG64(seed)`
    each (`surface_samples`), so two equal meshes give exactly 0; each mean
    is `math.fsum` over the squared distances. In the normalised meshes'
    units, before `CHAMFER_SCALE`.
    """
    ours = surface_samples(a, CHAMFER_SAMPLES, seed)
    theirs = surface_samples(b, CHAMFER_SAMPLES, seed)
    forward = math.fsum(nearest_squared(ours, theirs).tolist()) / len(ours)
    backward = math.fsum(nearest_squared(theirs, ours).tolist()) / len(theirs)
    return forward + backward


def field_metrics(
    model: arris.Model, candidate: arris.Body, target: arris.Body, *, seed: int
) -> FieldMetrics:
    """BenchCAD's `voxel_iou_64` and `chamfer_x1000` of `candidate` against `target`.

    Both bodies normalised to their own boxes (`normalised_mesh`), so the
    metrics see shape, not size or place. Raises the kernel's `ArrisError`
    where it cannot mesh a body, and what `normalised_mesh` and
    `surface_voxels` raise.
    """
    ours = normalised_mesh(model, candidate)
    theirs = normalised_mesh(model, target)
    return FieldMetrics(
        voxel_iou_64=voxel_iou(voxel_grid(ours), voxel_grid(theirs)),
        chamfer_x1000=CHAMFER_SCALE * chamfer(ours, theirs, seed=seed),
    )
