"""The mesh job: tessellate a delivered body for a picture.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
mesh worker, under the same limits as the other workers: the bytes are a
program's, so reading them is a kernel call on hostile input. Private.
"""

from __future__ import annotations

import math
import os

import arris

from arris_gym.sandbox._frame import MeshFrame
from arris_gym.sandbox._program import exception_line, read_all, write_frame
from arris_gym.sandbox.outcome import Status

# The chord tolerance of a picture's tessellation, as a fraction of the
# body's bounding-box diagonal: fine enough that a circle of a tenth of the
# part reads as round at 256 px, coarse enough to stay a few thousand triangles.
CHORD_FRACTION = 1 / 200


def tessellation(data: bytes) -> MeshFrame:
    """The body bytes `data` as a mesh frame; `runtime` where the kernel refuses. Never raises."""
    try:
        model = arris.Model()
        body = model.read_body(data).body
        bounds = model.bounds(body)
        if bounds is None:
            raise ValueError("the kernel reports no bounds for the body")
        low, high = bounds
        diagonal = math.dist(low, high)
        mesh = model.tessellate(body, diagonal * CHORD_FRACTION)
        positions, triangles = mesh.to_numpy()
        return MeshFrame(
            status=Status.OK,
            message="",
            positions=positions.astype("<f8").tobytes(),
            triangles=triangles.astype("<u4").tobytes(),
        )
    except BaseException as error:  # noqa: BLE001 - the kernel's refusals and MemoryError
        return MeshFrame(
            status=Status.RUNTIME, message=exception_line(error), positions=b"", triangles=b""
        )


def execute(payload_fd: int, result_fd: int) -> None:
    """Read the body bytes on `payload_fd`; write one frame to `result_fd`."""
    worker = os.getpid()  # a forked child writes no frame (`write_frame`)
    write_frame(result_fd, tessellation(read_all(payload_fd)), worker)
