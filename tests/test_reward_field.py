"""The field's metrics: BenchCAD's voxel IoU on 64³ and its Chamfer times 1000, by closed forms.

docs/plans/m4-reward.md step 7. A body against itself and a cube against its
double give 1 and 0 exactly (both metrics are scale-blind); a box's filled
voxels number what its normalised extent gives. The hole filling is held
against a breadth-first flood over random grids, and the subdivision
against cutting a whole mesh at once, as trimesh does.
"""

from __future__ import annotations

import collections
import functools
import json

import arris
import numpy as np
import numpy.typing as npt
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.reward import _field
from arris_gym.reward._field import (
    GRID_PADDING,
    GRID_RESOLUTION,
    centred,
    field_metrics,
    fill_holes,
    normalised_mesh,
    surface_voxels,
    voxel_grid,
    voxel_iou,
)

_Grid = npt.NDArray[np.bool_]
_Floats = npt.NDArray[np.float64]
REWARD_ROOT = fixture_cases.ROOT / "reward"
SLUGS = sorted(d.name for d in REWARD_ROOT.iterdir() if (d / "program.py").is_file())
SIDE = GRID_RESOLUTION + GRID_PADDING


@functools.cache
def _bytes(program: str) -> bytes:
    result = ag.run(program)
    assert result.status is ag.Status.OK, result.message
    assert result.body is not None
    return result.body.data


def _bodies(slug: str) -> tuple[arris.Model, arris.Body, arris.Body]:
    folder = REWARD_ROOT / slug
    model = arris.Model()
    a = model.read_body(_bytes((folder / "program.py").read_text(encoding="utf-8"))).body
    b = model.read_body(_bytes((folder / "target.py").read_text(encoding="utf-8"))).body
    return model, a, b


# --- closed forms --------------------------------------------------------------


@pytest.mark.parametrize("slug", SLUGS)
@pytest.mark.parametrize("side", ["program", "target"])
def test_a_body_against_itself_is_one_and_zero(slug: str, side: str) -> None:
    model, a, b = _bodies(slug)
    body = a if side == "program" else b
    got = field_metrics(model, body, body, seed=0)
    assert (got.voxel_iou_64, got.chamfer_x1000) == (1.0, 0.0)


def test_a_cube_against_its_double_is_one_and_zero_where_our_iou_is_an_eighth() -> None:
    model, a, b = _bodies("cube-and-double")
    got = field_metrics(model, a, b, seed=0)
    assert (got.voxel_iou_64, got.chamfer_x1000) == (1.0, 0.0)
    expected = json.loads((REWARD_ROOT / "cube-and-double" / "expected.json").read_text("utf-8"))
    assert expected["iou"] == 0.125
    scored = ag.score(
        ag.run((REWARD_ROOT / "cube-and-double" / "program.py").read_text("utf-8")),
        ag.BodyRef.of(_bytes((REWARD_ROOT / "cube-and-double" / "target.py").read_text("utf-8"))),
    )
    assert scored.iou == 0.125
    assert scored.field == ag.FieldMetrics(voxel_iou_64=1.0, chamfer_x1000=0.0)


def test_a_boxs_filled_voxels_are_its_normalised_extent() -> None:
    # A 4 by 2 by 1 box normalises to [0, 1], [0.25, 0.75] and [0.375, 0.625]:
    # its vertices round to voxels 0..64, 16..48 and 24..40 at a pitch of
    # 1/64, every one of the box between them filled.
    model = arris.Model()
    box = model.primitive_box((0, 0, 0), (4, 2, 1))[0]
    grid = voxel_grid(normalised_mesh(model, box))
    assert grid.shape == (SIDE, SIDE, SIDE)
    assert int(np.count_nonzero(grid)) == 65 * 33 * 17
    # Centred by its own shape: (68 - 65) // 2 = 1, (68 - 33) // 2 = 17, (68 - 17) // 2 = 25.
    assert np.array_equal(np.argwhere(grid).min(axis=0), [1, 17, 25])


def test_a_box_and_its_double_in_one_direction_differ_as_their_grids_count() -> None:
    model = arris.Model()
    cube = model.primitive_box((0, 0, 0), (1, 1, 1))[0]
    slab = model.primitive_box((0, 0, 0), (2, 2, 1))[0]
    got = field_metrics(model, cube, slab, seed=0)
    # 65³ against 65 by 65 by 33, the slab's voxels all inside the cube's.
    assert got.voxel_iou_64 == (65 * 65 * 33) / 65**3
    assert got.chamfer_x1000 > 0.0


def test_the_metrics_are_the_same_on_a_repeat() -> None:
    model, a, b = _bodies("iou-third")
    assert field_metrics(model, a, b, seed=3) == field_metrics(model, a, b, seed=3)


# --- the hole filling ------------------------------------------------------------


def _flood(shell: _Grid) -> _Grid:
    """The reference: a breadth-first flood of empty cells from the border, faces only."""
    outside = np.zeros_like(shell)
    queue: collections.deque[tuple[int, int, int]] = collections.deque()
    for cell in np.argwhere(~shell):
        if any(c == 0 or c == n - 1 for c, n in zip(cell, shell.shape, strict=True)):
            outside[tuple(cell)] = True
            queue.append((int(cell[0]), int(cell[1]), int(cell[2])))
    while queue:
        x, y, z = queue.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + dx, y + dy, z + dz)
            inside = all(0 <= c < s for c, s in zip(n, shell.shape, strict=True))
            if inside and not shell[n] and not outside[n]:
                outside[n] = True
                queue.append(n)
    return ~outside


@settings(max_examples=150, deadline=None)
@given(
    shape=st.tuples(*(st.integers(1, 9),) * 3),
    density=st.floats(0.0, 0.9),
    seed=st.integers(0, 2**32 - 1),
)
def test_filling_holes_is_a_flood_from_the_border(
    shape: tuple[int, int, int], density: float, seed: int
) -> None:
    rng = np.random.Generator(np.random.PCG64(seed))
    shell = rng.random(shape) < density
    assert np.array_equal(fill_holes(shell), _flood(shell))


def test_a_closed_shell_is_filled_and_an_open_cup_is_not() -> None:
    shell = np.ones((5, 5, 5), dtype=np.bool_)
    shell[1:4, 1:4, 1:4] = False
    assert np.count_nonzero(fill_holes(shell)) == 125
    cup = shell.copy()
    cup[2, 2, 4] = False  # a hole in the lid
    assert np.array_equal(fill_holes(cup), cup)


def test_centring_crops_a_grid_too_large() -> None:
    grid = np.ones((3, 5, 1), dtype=np.bool_)
    out = centred(grid, 4)
    assert out.shape == (4, 4, 4)
    assert np.array_equal(np.argwhere(out).min(axis=0), [0, 0, 1])
    assert np.count_nonzero(out) == 3 * 4 * 1


def test_voxel_iou_of_empty_grids_is_zero() -> None:
    empty = np.zeros((2, 2, 2), dtype=np.bool_)
    assert voxel_iou(empty, empty) == 0.0


# --- the subdivision -------------------------------------------------------------


def _whole_mesh_hits(mesh: tuple[_Floats, _Floats, _Floats]) -> set[tuple[int, int, int]]:
    """trimesh's `subdivide_to_size` on the whole mesh: shared midpoints, each vertex rounded."""
    pitch = 1.0 / GRID_RESOLUTION
    vertices: list[tuple[float, float, float]] = []
    index: dict[tuple[float, float, float], int] = {}

    def vid(p: _Floats) -> int:
        key = (float(p[0]), float(p[1]), float(p[2]))
        if key not in index:
            index[key] = len(vertices)
            vertices.append(key)
        return index[key]

    faces = [(vid(a), vid(b), vid(c)) for a, b, c in zip(*mesh, strict=True)]
    hits: set[tuple[int, int, int]] = set()
    while faces:
        v = np.array(vertices)
        f = np.array(faces)
        edges = np.sqrt((np.diff(v[f[:, [0, 1, 2, 0]]], axis=1) ** 2).sum(axis=2))
        long = (edges > pitch / 2.0).any(axis=1)
        for corner in v[f[~long].ravel()]:
            x, y, z = (int(i) for i in np.rint(corner / pitch))
            hits.add((x, y, z))
        next_faces = []
        for a, b, c in f[long]:
            ab = vid((v[a] + v[b]) / 2.0)
            bc = vid((v[b] + v[c]) / 2.0)
            ca = vid((v[c] + v[a]) / 2.0)
            next_faces += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        faces = next_faces
    return hits


def _hit_set(grid: _Grid, low: npt.NDArray[np.int64]) -> set[tuple[int, int, int]]:
    return {(int(x), int(y), int(z)) for x, y, z in np.argwhere(grid) + low}


def test_cutting_each_triangle_alone_hits_what_cutting_the_mesh_hits() -> None:
    # A strip of triangles sharing edges, each up to 0.08 a side, so the
    # reference's Python loop meets a few thousand triangles.
    rng = np.random.Generator(np.random.PCG64(7))
    row = np.linspace(0.1, 0.9, 12)
    top = np.stack([row, np.full(12, 0.5), rng.random(12) * 0.04 + 0.5], axis=1)
    bottom = np.stack([row + 0.03, np.full(12, 0.43), rng.random(12) * 0.04 + 0.5], axis=1)
    a = np.concatenate((top[:-1], bottom[:-1]))
    b = np.concatenate((bottom[:-1], bottom[1:]))
    c = np.concatenate((top[1:], top[1:]))
    mesh = (a, b, c)
    want = _whole_mesh_hits(mesh)
    got = surface_voxels(mesh)
    low = np.array([min(h[i] for h in want) for i in range(3)])
    assert _hit_set(got, low) == want


def test_the_chunk_moves_no_voxel(monkeypatch: pytest.MonkeyPatch) -> None:
    model, a, _ = _bodies("cone-shifted")
    mesh = normalised_mesh(model, a)
    want = surface_voxels(mesh)
    monkeypatch.setattr(_field, "SUBDIVIDE_CHUNK", 7)
    assert np.array_equal(surface_voxels(mesh), want)


def test_a_mesh_too_coarse_for_the_cap_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    model = arris.Model()
    mesh = normalised_mesh(model, model.primitive_box((0, 0, 0), (1, 1, 1))[0])
    monkeypatch.setattr(_field, "MAX_SUBDIVISIONS", 2)
    with pytest.raises(ValueError, match="max_iter exceeded"):
        surface_voxels(mesh)
