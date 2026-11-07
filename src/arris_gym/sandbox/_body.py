"""The body job: read a program's body bytes back, check and measure them.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
body worker, under the same limits as a program worker, never in the
caller's process: the bytes came from a program worker, which a program
controls, so reading them is a kernel call on hostile input (ADR-0002). The
worker reads them into a fresh model, runs `check(body, "full")` and the
measures, and writes one `BodyFrame` to the result pipe. Private.
"""

from __future__ import annotations

import arris

from arris_gym.sandbox._frame import BodyFrame
from arris_gym.sandbox._program import exception_line, read_all, write_all
from arris_gym.sandbox.outcome import Measures, Status

# The level of the checker every delivered body must pass.
CHECK_LEVEL = "full"
# The message of a body that `read_body` accepted and the full check did not:
# the violations themselves are the checker's words.
FAILED_FULL_CHECK = f'the body read back fails check(body, "{CHECK_LEVEL}")'


def _violations(report: arris.Report) -> tuple[str, ...]:
    """The checker's violations, each as the kernel writes it."""
    return tuple(str(v) for v in report.violations)


def _measures(model: arris.Model, body: arris.Body, report: arris.Report) -> Measures:
    mass = model.mass_properties(body)
    bounds = model.bounds(body)
    if bounds is None:
        raise ValueError("the kernel reports no bounds for the body")
    euler = report.euler
    if euler is None:
        raise ValueError("the kernel reports no Euler line for the body")
    kinds: dict[str, int] = {}
    for face in model.faces(body):
        kind = model.surface(face).kind
        kinds[kind] = kinds.get(kind, 0) + 1
    return Measures(
        volume=mass.volume,
        area=mass.area,
        centroid=mass.centroid,
        bounds=bounds,
        faces=euler.faces,
        shells=euler.shells,
        genus=euler.genus,
        face_kinds=tuple(sorted(kinds.items())),
    )


def _verdict(data: bytes) -> BodyFrame:
    model = arris.Model()
    try:
        body = model.read_body(data).body
    except arris.BodyRejectedError as error:
        return BodyFrame(
            status=Status.CHECKER_FAIL,
            message=str(error),
            measures=None,
            violations=_violations(error.report),
        )
    report = model.check(body, CHECK_LEVEL)
    if not report.ok:
        return BodyFrame(
            status=Status.CHECKER_FAIL,
            message=FAILED_FULL_CHECK,
            measures=None,
            violations=_violations(report),
        )
    return BodyFrame(
        status=Status.OK, message="", measures=_measures(model, body, report), violations=()
    )


def verdict(data: bytes) -> BodyFrame:
    """What the body bytes `data` are: ok with measures, checker_fail, or runtime.

    `BodyRejectedError` from `read_body` is `checker_fail` with its report's
    violations, as is a body the full check refuses; any other error, while
    reading or measuring, is `runtime` with Python's own line for it. Never
    raises.
    """
    try:
        return _verdict(data)
    except BaseException as error:  # noqa: BLE001 - MemoryError and the kernel's other refusals
        return BodyFrame(
            status=Status.RUNTIME,
            message=exception_line(error),
            measures=None,
            violations=(),
            out_of_memory=isinstance(error, MemoryError),
        )


def execute(payload_fd: int, result_fd: int) -> None:
    """Read the body bytes on `payload_fd`; write one frame to `result_fd`."""
    write_all(result_fd, verdict(read_all(payload_fd)).model_dump_json().encode())
