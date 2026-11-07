"""The program job: run one program's text inside a program worker.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
program worker, never in the caller's process. The program's text comes
from a descriptor the caller filled; the worker classifies how it ended, by
the type of what it raised and never by a message's wording, and writes one
`ProgramFrame` to the result pipe: a body's bytes, which a body worker
reads back (`sandbox/_body.py`), or the failure. Private.
"""

from __future__ import annotations

import os
import traceback

import arris
import arris.build

from arris_gym.cq import UnsupportedApi
from arris_gym.sandbox._frame import ProgramFrame
from arris_gym.sandbox.outcome import ArrisRefusal, Status

# The program's text is decoded so that every string a caller can pass
# round-trips, lone surrogates included; `compile` refuses what it cannot
# encode, and that is the program's own failure.
TEXT_ERRORS = "surrogatepass"
# The name a program binds its solid to (ARCHITECTURE.md §Outcomes).
RESULT_NAME = "result"
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


def exception_line(error: BaseException) -> str:
    """Python's own account of an exception: type and message, verbatim."""
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def _deliver(solid: arris.build.Solid) -> ProgramFrame:
    """The frame for a program that ended with `solid`: its body's bytes.

    Nothing is checked or measured here: the program can reach everything in
    this process, `solid.model` included, so the bytes go to a body worker.
    """
    data = solid.model.write_body(solid.body)
    return ProgramFrame(status=Status.OK, message="", refusal=None, body=data)


def _failure(status: Status, message: str, refusal: ArrisRefusal | None = None) -> ProgramFrame:
    return ProgramFrame(status=status, message=message, refusal=refusal, body=None)


def classify(text: str) -> ProgramFrame:
    """Compile and run `text`; the frame saying how it ended. Never raises.

    The decision is by type: `SyntaxError` (or text `compile` cannot encode)
    from `compile`, `UnsupportedApi`, an `arris.ArrisError`, any other
    exception, a program that binds no `result` or one that is not a `Solid`.
    """
    try:
        code = compile(text, _SOURCE_NAME, "exec")
    except (SyntaxError, UnicodeEncodeError) as error:
        return _failure(Status.SYNTAX, exception_line(error))
    except BaseException as error:  # noqa: BLE001 - RecursionError, MemoryError: the program's
        return _failure(Status.RUNTIME, exception_line(error))
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
        return _failure(Status.RUNTIME, exception_line(error))
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
