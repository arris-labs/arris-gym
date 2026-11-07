"""A mesh as a picture: a z-buffer on `numpy`, four fixed views, a PNG by `zlib`.

Orthographic views from fixed directions, each fitted to the mesh's bounding
sphere so that the same mesh always lands on the same pixels. A picture is
for the agent's eyes (`inspect` skill): nothing scores it, so it uses no
dependency beyond `numpy`. Private; `arris_gym.dump_png` is the public name.
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

# One view is PANEL x PANEL pixels; the sheet lays the views out in a grid
# of SHEET_COLUMNS, so its size does not depend on the part.
PANEL = 256
SHEET_COLUMNS = 2
# The part's bounding sphere fills this fraction of a panel's side.
FILL = 0.8
# Shades, 0 to 255: the paper, and the least light a face turned from the
# light gets.
BACKGROUND = 245
AMBIENT = 0.25
# A fixed light, in each view's own (right, up, toward-viewer) axes.
LIGHT = (0.3, 0.5, 0.8)
# Triangles whose projected area is below this many square pixels cover no
# pixel centre worth drawing (and would divide by nothing).
MIN_PROJECTED_AREA = 1e-12

Floats = NDArray[np.float64]
Vec = tuple[float, float, float]


@dataclass(frozen=True)
class View:
    """A direction to look from: the screen's right and up and the vector toward the viewer."""

    name: str
    right: Vec
    up: Vec
    toward: Vec


_ISO = 1 / math.sqrt(3)
_ISO_RIGHT = 1 / math.sqrt(2)
_ISO_UP = 1 / math.sqrt(6)

# Front looks along +Y, right along -X, top down along -Z, and the last from
# the +X, -Y, +Z octant; z is up wherever the view has an up in z.
VIEWS = (
    View("front", (1, 0, 0), (0, 0, 1), (0, -1, 0)),
    View("right", (0, 1, 0), (0, 0, 1), (1, 0, 0)),
    View("top", (1, 0, 0), (0, 1, 0), (0, 0, 1)),
    View(
        "iso",
        (_ISO_RIGHT, _ISO_RIGHT, 0),
        (-_ISO_UP, _ISO_UP, 2 * _ISO_UP),
        (_ISO, -_ISO, _ISO),
    ),
)


@dataclass(frozen=True)
class Panel:
    """One view's raster: `depth` (nearest toward-coordinate per pixel, -inf
    where nothing is drawn) and `shade` (0 to 255), both PANEL x PANEL, row 0 on top."""

    view: View
    scale: float
    depth: Floats
    shade: NDArray[np.uint8]

    @property
    def covered(self) -> NDArray[np.bool_]:
        """Where the part is drawn: its silhouette."""
        covered: NDArray[np.bool_] = np.isfinite(self.depth)
        return covered


def _project(points: Floats, axis: Vec) -> Floats:
    # Explicit sums, not a dot product: no BLAS on the path.
    projected: Floats = points[:, 0] * axis[0] + points[:, 1] * axis[1] + points[:, 2] * axis[2]
    return projected


def fit_scale(radius: float) -> float:
    """Pixels per model unit for a part whose bounding sphere has `radius`."""
    return FILL * PANEL / (2 * radius) if radius > 0 else 1.0


def _panel(view: View, positions: Floats, triangles: NDArray[np.uint32]) -> Panel:
    low, high = positions.min(axis=0), positions.max(axis=0)
    centre = (low + high) / 2
    radius = float(np.sqrt(((high - low) ** 2).sum())) / 2
    scale = fit_scale(radius)
    shifted = positions - centre
    screen_x = PANEL / 2 + scale * _project(shifted, view.right)
    screen_y = PANEL / 2 - scale * _project(shifted, view.up)
    near = _project(shifted, view.toward)
    light = np.array(LIGHT) / math.sqrt(sum(c * c for c in LIGHT))
    depth = np.full((PANEL, PANEL), -np.inf)
    shade = np.full((PANEL, PANEL), BACKGROUND, dtype=np.uint8)
    for a, b, c in triangles.astype(np.int64):
        x = screen_x[[a, b, c]]
        y = screen_y[[a, b, c]]
        z = near[[a, b, c]]
        area = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        if abs(area) < MIN_PROJECTED_AREA:
            continue
        # The normal in view axes, from the world-space triangle.
        edge1, edge2 = shifted[b] - shifted[a], shifted[c] - shifted[a]
        normal = np.cross(edge1, edge2)
        length = math.sqrt(float((normal * normal).sum()))
        if length == 0:
            continue
        in_view = np.array(
            [_project(normal[None], view.right)[0], _project(normal[None], view.up)[0],
             _project(normal[None], view.toward)[0]]
        )  # fmt: skip
        lit = abs(float((in_view * light).sum())) / length
        grey = round(255 * 0.7 * (AMBIENT + (1 - AMBIENT) * lit))
        x0 = max(math.floor(x.min() - 0.5), 0)
        x1 = min(math.ceil(x.max() - 0.5) + 1, PANEL)
        y0 = max(math.floor(y.min() - 0.5), 0)
        y1 = min(math.ceil(y.max() - 0.5) + 1, PANEL)
        if x0 >= x1 or y0 >= y1:
            continue
        px = np.arange(x0, x1) + 0.5
        py = (np.arange(y0, y1) + 0.5)[:, None]
        w1 = ((px - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (py - y[0])) / area
        w2 = ((x[1] - x[0]) * (py - y[0]) - (px - x[0]) * (y[1] - y[0])) / area
        w0 = 1 - w1 - w2
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        d = w0 * z[0] + w1 * z[1] + w2 * z[2]
        window = depth[y0:y1, x0:x1]
        nearer = inside & (d > window)
        window[nearer] = d[nearer]
        shade[y0:y1, x0:x1][nearer] = grey
    return Panel(view, scale, depth, shade)


def render(positions: Floats, triangles: NDArray[np.uint32]) -> tuple[Panel, ...]:
    """The mesh drawn from each of `VIEWS`, in order."""
    return tuple(_panel(view, positions, triangles) for view in VIEWS)


def sheet(panels: tuple[Panel, ...]) -> NDArray[np.uint8]:
    """The panels in a grid, a grey image of fixed size, row 0 on top."""
    rows = -(-len(panels) // SHEET_COLUMNS)
    image = np.full((rows * PANEL, SHEET_COLUMNS * PANEL), BACKGROUND, dtype=np.uint8)
    for index, panel in enumerate(panels):
        row, column = divmod(index, SHEET_COLUMNS)
        image[row * PANEL : (row + 1) * PANEL, column * PANEL : (column + 1) * PANEL] = panel.shade
    return image


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """An 8-bit greyscale PNG of `image`, unfiltered, deflated at a fixed level."""
    height, width = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
