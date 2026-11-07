"""The program job: run one program's text inside a program worker.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
program worker, never in the caller's process. The program's text comes
from a descriptor the caller filled; the worker classifies how it ended, by
the type of what it raised and never by a message's wording, and writes one
`Frame` to the result pipe. Private.
"""

from __future__ import annotations

import os
import traceback

import arris
import arris.build

from arris_gym.cq import UnsupportedApi
from arris_gym.sandbox._frame import Frame
from arris_gym.sandbox.outcome import ArrisRefusal, Measures, Status

# The program's text is decoded so that every string a caller can pass
# round-trips, lone surrogates included; `compile` refuses what it cannot
# encode, and that is the program's own failure.
TEXT_ERRORS = "surrogatepass"
# The name a program binds its solid to (ARCHITECTURE.md §Outcomes).
RESULT_NAME = "result"
# The level of the checker every delivered body must pass.
CHECK_LEVEL = "full"
_SOURCE_NAME = "<program>"


def read_all(fd: int) -> bytes:
    """Every byte left on `fd`, to its end; closes it."""
    chunks = []
    try:
        while chunk := os.read(fd, 1 << 20):
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def write_all(fd: int, data: bytes) -> None:
    """Write `data` to `fd` whole."""
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def entity_name(entity: object) -> str:
    """An entity as the kernel's messages write it: sign, kind letter, index.

    `+e0` is edge 0 in its natural sense, `-f2` face 2 reversed. A handle of
    a kind the messages have no letter for keeps its `repr`.
    """
    letter = {
        arris.Edge: "e",
        arris.Face: "f",
        arris.Vertex: "v",
        arris.Shell: "s",
    }.get(type(entity))
    if letter is None:
        return repr(entity)
    sign = "-" if getattr(entity, "reversed", False) else "+"
    return f"{sign}{letter}{getattr(entity, 'index')}"  # noqa: B009 - index is on every handle


def _refusal(error: arris.ArrisError) -> ArrisRefusal:
    """The refusal an `ArrisError` is: its class, its `str()`, its entity fields."""
    named: list[object] = []
    single = getattr(error, "entity", None)
    if single is not None:
        named.append(single)
    named.extend(getattr(error, "entities", None) or ())
    return ArrisRefusal(
        kind=type(error).__name__,
        message=_text(error),
        entities=tuple(entity_name(e) for e in named),
    )


def _text(error: BaseException) -> str:
    try:
        return str(error)
    except BaseException:  # noqa: BLE001 - a hostile __str__ is the program's failure
        return f"<{type(error).__name__}.__str__ failed>"


def _exception_line(error: BaseException) -> str:
    """Python's own account of an exception: type and message, verbatim."""
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def _measures(solid: arris.build.Solid) -> Measures:
    model, body = solid.model, solid.body
    mass = model.mass_properties(body)
    bounds = model.bounds(body)
    if bounds is None:
        raise ValueError("the kernel reports no bounds for the result")
    euler = model.check(body, CHECK_LEVEL).euler
    if euler is None:
        raise ValueError("the kernel reports no Euler line for the result")
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


def _deliver(solid: arris.build.Solid) -> Frame:
    """The frame for a program that ended with `solid`: ok, or checker_fail."""
    model, body = solid.model, solid.body
    report = model.check(body, CHECK_LEVEL)
    data = model.write_body(body)
    if not report.ok:
        violations = tuple(
            f"{v.code} at {entity_name(v.entity)} ({v.level})" for v in report.violations
        )
        return Frame(
            status=Status.CHECKER_FAIL,
            message="the body failed the checker",
            refusal=None,
            body=data,
            measures=None,
            violations=violations,
        )
    return Frame(
        status=Status.OK,
        message="",
        refusal=None,
        body=data,
        measures=_measures(solid),
        violations=(),
    )


def _failure(status: Status, message: str, refusal: ArrisRefusal | None = None) -> Frame:
    return Frame(
        status=status,
        message=message,
        refusal=refusal,
        body=None,
        measures=None,
        violations=(),
    )


def classify(text: str) -> Frame:
    """Compile and run `text`; the frame saying how it ended. Never raises.

    The decision is by type: `SyntaxError` (or text `compile` cannot encode)
    from `compile`, `UnsupportedApi`, an `arris.ArrisError`, any other
    exception, a program that binds no `result` or one that is not a `Solid`.
    """
    try:
        code = compile(text, _SOURCE_NAME, "exec")
    except (SyntaxError, UnicodeEncodeError) as error:
        return _failure(Status.SYNTAX, _exception_line(error))
    except BaseException as error:  # noqa: BLE001 - RecursionError, MemoryError: the program's
        return _failure(Status.RUNTIME, _exception_line(error))
    namespace: dict[str, object] = {"__name__": "__program__"}
    try:
        exec(code, namespace)  # inside the worker only
        result = namespace.get(RESULT_NAME)
        if isinstance(result, arris.build.Solid):
            return _deliver(result)
    except UnsupportedApi as error:
        return _failure(Status.UNSUPPORTED_API, _text(error))
    except arris.ArrisError as error:
        return _failure(Status.ARRIS_REFUSAL, _text(error), _refusal(error))
    except BaseException as error:  # noqa: BLE001 - SystemExit and MemoryError included
        return _failure(Status.RUNTIME, _exception_line(error))
    if RESULT_NAME not in namespace:
        return _failure(Status.RUNTIME, f"the program ended without binding `{RESULT_NAME}`")
    return _failure(
        Status.RUNTIME,
        f"`{RESULT_NAME}` is of type {type(result).__name__}, not arris.build.Solid",
    )


def execute(payload_fd: int, result_fd: int) -> None:
    """Run the program on `payload_fd`; write one frame to `result_fd`."""
    text = read_all(payload_fd).decode("utf-8", TEXT_ERRORS)
    write_all(result_fd, classify(text).model_dump_json().encode())
