"""The program job: run one program's text inside a program worker.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
program worker, never in the caller's process. The program's text comes
from a descriptor the caller filled; what the program built goes to the
result pipe. Private.
"""

from __future__ import annotations

import os

import arris.build

# The program's text is decoded so that every string a caller can pass
# round-trips, lone surrogates included; `compile` refuses what it cannot
# encode, and that is the program's own failure.
TEXT_ERRORS = "surrogatepass"


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


def execute(payload_fd: int, result_fd: int) -> None:
    """Run the program on `payload_fd`; write its `result`'s body bytes.

    The text is compiled and executed in a fresh namespace. When it binds
    `result` to an `arris.build.Solid`, the bytes of that solid's
    `write_body` go to `result_fd`; otherwise nothing does. An exception
    the program raises propagates: the worker's exit code says so.
    """
    text = read_all(payload_fd).decode("utf-8", TEXT_ERRORS)
    namespace: dict[str, object] = {"__name__": "__program__"}
    exec(compile(text, "<program>", "exec"), namespace)  # inside the worker only
    result = namespace.get("result")
    if isinstance(result, arris.build.Solid):
        write_all(result_fd, result.model.write_body(result.body))
