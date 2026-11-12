"""The program job: run one program's text inside a program worker.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
program worker, never in the caller's process. The program's dialect and
text come from a descriptor the caller filled (`payload`): under `cq` the
worker installs `arris_gym.cq`'s CadQuery names and gives the program
`show_object` (ADR-0007). The worker classifies how it ended, by
the type of what it raised and never by a message's wording, and writes one
`ProgramFrame` to the result pipe: a body's bytes, which a body worker
reads back (`sandbox/_body.py`), or the failure. Private.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import assert_never

import arris
import arris.build
from pydantic import BaseModel

from arris_gym.cq import UnsupportedApi
from arris_gym.cq._module import program_module
from arris_gym.cq._result import NotASolid, solid_of
from arris_gym.sandbox._frame import ProgramFrame
from arris_gym.sandbox.outcome import ArrisRefusal, Dialect, Status

# The program's text is decoded so that every string a caller can pass
# round-trips, lone surrogates included; `compile` refuses what it cannot
# encode, and that is the program's own failure.
TEXT_ERRORS = "surrogatepass"
# The name a program binds its solid to (ARCHITECTURE.md §Outcomes).
RESULT_NAME = "result"
# What a `cq` program shows its result with, and the module it imports (ADR-0007).
SHOW_NAME = "show_object"
CADQUERY = "cadquery"
_SOURCE_NAME = "<program>"
# A program job's payload opens with one byte naming its dialect; the
# program's text follows. Only the caller writes a payload.
_DIALECT_BYTES = {Dialect.ARRIS: b"a", Dialect.CQ: b"c"}
_DIALECTS = {code: dialect for dialect, code in _DIALECT_BYTES.items()}


def payload(dialect: Dialect, text: bytes) -> bytes:
    """A program job's payload: the dialect's byte, then the program's encoded text."""
    return _DIALECT_BYTES[dialect] + text


def read_payload(data: bytes) -> tuple[Dialect, str]:
    """The dialect and text of a program job's payload `data`.

    Raises `KeyError` for a first byte that names no dialect: the caller's
    bug, so the worker ends with no frame and the job is a `crash`.
    """
    return _DIALECTS[data[:1]], data[1:].decode("utf-8", TEXT_ERRORS)


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


def write_frame(fd: int, frame: BaseModel, worker: int) -> None:
    """Write `frame` to `fd` as JSON, but only from the process `worker`.

    `worker` is the pid the job's worker read when it started: PID 1 of its
    namespace. A program can fork, and a child returns through the same
    code with the result pipe inherited; it writes nothing here, so a job's
    pipe carries the worker's one frame whatever the scheduling. A child
    that writes the pipe itself is the program's own forgery, refused when
    the frame is parsed.
    """
    if os.getpid() == worker:
        write_all(fd, frame.model_dump_json().encode())


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


def refusal_of(error: arris.ArrisError) -> ArrisRefusal:
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


def _failure(
    status: Status,
    message: str,
    refusal: ArrisRefusal | None = None,
    *,
    error: BaseException | None = None,
) -> ProgramFrame:
    """A failure's frame; `error`, if any, is what it ended on (a `MemoryError` is marked)."""
    return ProgramFrame(
        status=status,
        message=message,
        refusal=refusal,
        body=None,
        out_of_memory=isinstance(error, MemoryError),
    )


class _NoCadquerySubmodule(importlib.abc.MetaPathFinder):
    """Refuses `import cadquery.<name>`: the subset has no submodules (ADR-0007)."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.startswith(CADQUERY + "."):
            raise UnsupportedApi("cq." + fullname.removeprefix(CADQUERY + ".").split(".")[0])
        return None


def _install_cadquery() -> None:
    """Install the program-facing `cq` names, in this worker only."""
    sys.modules[CADQUERY] = program_module()
    sys.meta_path.insert(0, _NoCadquerySubmodule())


def _show_object(shown: list[object]) -> Callable[..., None]:
    """The `show_object` a `cq` program calls: it records what it is shown."""

    def show_object(obj: object, name: object = None, options: object = None) -> None:
        shown.append(obj)

    return show_object


def _cq_result(namespace: dict[str, object], shown: list[object]) -> arris.build.Solid:
    """The last `show_object` argument's solid, else `result`'s, else `r`'s.

    Selection is by binding presence, never validity (ADR-0015). Raises
    `NotASolid` (`runtime`) as `solid_of` does; a compound is one solid
    (ADR-0016).
    """
    if shown:
        return solid_of(shown[-1], f"the last `{SHOW_NAME}` argument")
    for name in (RESULT_NAME, "r"):
        if name in namespace:
            return solid_of(namespace[name], f"`{name}`")
    raise NotASolid(
        f"the program ended without calling `{SHOW_NAME}` or binding `{RESULT_NAME}` or `r`"
    )


def _arris_result(namespace: dict[str, object]) -> arris.build.Solid | ProgramFrame:
    """An `arris` program's solid, its module-level `result`, or the failure it is."""
    result = namespace.get(RESULT_NAME)
    if isinstance(result, arris.build.Solid):
        return result
    if RESULT_NAME not in namespace:
        return _failure(Status.RUNTIME, f"the program ended without binding `{RESULT_NAME}`")
    return _failure(
        Status.RUNTIME,
        f"`{RESULT_NAME}` is of type {type(result).__name__}, not arris.build.Solid",
    )


def classify(text: str, dialect: Dialect) -> ProgramFrame:
    """Compile and run `text` in `dialect`; the frame saying how it ended. Never raises.

    The decision is by type: `SyntaxError` (or text `compile` cannot encode)
    from `compile`, `UnsupportedApi`, an `arris.ArrisError`, any other
    exception, or a result that is not a solid: under `arris` a `result`
    missing or not a `Solid`, under `cq` one that does not resolve to a
    solid (ADR-0007; a compound is one, ADR-0016).
    """
    try:
        code = compile(text, _SOURCE_NAME, "exec")
    except (SyntaxError, UnicodeEncodeError) as error:
        return _failure(Status.SYNTAX, exception_line(error))
    except BaseException as error:  # noqa: BLE001 - RecursionError, MemoryError: the program's
        return _failure(Status.RUNTIME, exception_line(error), error=error)
    namespace: dict[str, object] = {"__name__": "__program__"}
    shown: list[object] = []
    if dialect is Dialect.CQ:
        _install_cadquery()
        namespace[SHOW_NAME] = _show_object(shown)
    try:
        exec(code, namespace)  # inside the worker only
        match dialect:
            case Dialect.ARRIS:
                found = _arris_result(namespace)
            case Dialect.CQ:
                found = _cq_result(namespace, shown)
            case unreachable:
                assert_never(unreachable)
        if isinstance(found, ProgramFrame):
            return found
        return _deliver(found)
    except UnsupportedApi as error:
        return _failure(Status.UNSUPPORTED_API, _text(error))
    except NotASolid as error:
        return _failure(Status.RUNTIME, _text(error))
    except arris.ArrisError as error:
        return _failure(Status.ARRIS_REFUSAL, _text(error), refusal_of(error))
    except BaseException as error:  # noqa: BLE001 - SystemExit and MemoryError included
        return _failure(Status.RUNTIME, exception_line(error), error=error)


def execute(payload_fd: int, result_fd: int) -> None:
    """Run the program on `payload_fd`; write one frame to `result_fd`.

    Only this worker writes it, not a child the program forked (`write_frame`).
    """
    worker = os.getpid()
    dialect, text = read_payload(read_all(payload_fd))
    write_frame(result_fd, classify(text, dialect), worker)
