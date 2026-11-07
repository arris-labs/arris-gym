"""`dump_png`: a result's body as a picture, through a mesh worker.

The body's bytes go to a mesh worker (`sandbox/_mesh.py`), which tessellates
them in isolation; the caller then parses the answer as it parses every
frame, trusting nothing, and draws it (`sandbox/_render.py`). Private; the
public name is re-exported by `arris_gym`.
"""

from __future__ import annotations

import os
import time

import numpy as np
import pydantic
from numpy.typing import NDArray

from arris_gym.sandbox import _render, _run
from arris_gym.sandbox._frame import MeshFrame
from arris_gym.sandbox._zygote import JobKind, Zygote
from arris_gym.sandbox.outcome import ExecResult, Status

_POSITION_BYTES = 3 * 8
_TRIANGLE_BYTES = 3 * 4


class PictureError(RuntimeError):
    """The body of a result could not be drawn; the message says why, verbatim from the worker."""


def _mesh(
    zygote: Zygote, data: bytes, timeout: float, memory: int
) -> tuple[NDArray[np.float64], NDArray[np.uint32]]:
    outcome = zygote.execute(JobKind.MESH, data, deadline=time.monotonic() + timeout, memory=memory)
    early = _run.ended(outcome, "mesh worker", timeout)
    if early is not None:
        raise PictureError(early.message)
    try:
        frame = MeshFrame.model_validate_json(outcome.data)
    except pydantic.ValidationError:
        raise PictureError("the mesh worker delivered a result that is not a valid frame") from None
    if frame.status is not Status.OK:
        raise PictureError(frame.message)
    if len(frame.positions) % _POSITION_BYTES or len(frame.triangles) % _TRIANGLE_BYTES:
        raise PictureError("the mesh worker delivered a mesh of the wrong shape")
    positions = np.frombuffer(frame.positions, dtype="<f8").reshape(-1, 3).astype(np.float64)
    triangles = np.frombuffer(frame.triangles, dtype="<u4").reshape(-1, 3).astype(np.uint32)
    if not np.isfinite(positions).all() or int(triangles.max()) >= len(positions):
        raise PictureError("the mesh worker delivered a mesh that is not a mesh of its points")
    return positions, triangles


def draw(
    zygote: Zygote, result: ExecResult, path: str | os.PathLike[str], timeout: float, memory: int
) -> None:
    """Write the picture of `result`'s body to `path`; see `arris_gym.dump_png`."""
    if result.body is None:
        raise ValueError(f"a result with status {result.status.value} has no body to draw")
    positions, triangles = _mesh(zygote, result.body.data, timeout, memory)
    image = _render.sheet(_render.render(positions, triangles))
    with open(path, "wb") as out:
        out.write(_render.encode_png(image))
