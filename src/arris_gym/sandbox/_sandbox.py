"""`Sandbox`, `run` and `run_many`: the public ways to run programs.

A `Sandbox` owns one zygote, started on first use, and bounds how many
programs are alive at once. `run` and `run_many` are the same calls on a
process-wide default instance.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from arris_gym.sandbox import _run
from arris_gym.sandbox._zygote import Zygote
from arris_gym.sandbox.outcome import Dialect, ExecResult

# The most programs alive at once when the caller does not say: one per core,
# capped, since each live program holds up to `memory` bytes of address space.
DEFAULT_WORKERS_CAP = 32


def _check_workers(workers: int | None) -> int:
    """The number of live forks `workers` asks for, or the caller's mistake."""
    if workers is None:
        return max(1, min(DEFAULT_WORKERS_CAP, os.cpu_count() or 1))
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError(f"workers must be a positive number, got {workers!r}")
    return workers


class Sandbox:
    """Runs programs, each alone in an isolated process.

    The zygote starts on first use and `close` stops it. Every method is
    safe to call from several threads at once. Like `arris_gym.run`, none
    raises on a program; a caller's mistake raises `ValueError` and a
    machine that cannot isolate a program raises `SandboxUnavailable`.

    >>> from arris_gym import Sandbox, Status
    >>> with Sandbox() as sandbox:
    ...     [r.status.value for r in sandbox.run_many(["result = (", "x = 1"])]
    ['syntax', 'runtime']
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._zygote: Zygote | None = None
        self._closed = False

    def _live_zygote(self) -> Zygote:
        with self._lock:
            if self._closed:
                raise RuntimeError("this Sandbox is closed")
            if self._zygote is None:
                self._zygote = Zygote()
            return self._zygote

    def run(
        self,
        program: str,
        *,
        dialect: Dialect | str = Dialect.ARRIS,
        timeout: float = _run.DEFAULT_TIMEOUT,
        memory: int = _run.DEFAULT_MEMORY,
    ) -> ExecResult:
        """Run one program; see `arris_gym.run`."""
        resolved = _run.check_arguments(dialect, timeout, memory)
        if not isinstance(program, str):
            raise TypeError(f"program must be text, got {type(program).__name__}")
        return _run.run_program(
            self._live_zygote(), program, resolved, timeout=timeout, memory=memory
        )

    def run_many(
        self,
        programs: Iterable[str],
        *,
        dialect: Dialect | str = Dialect.ARRIS,
        timeout: float = _run.DEFAULT_TIMEOUT,
        memory: int = _run.DEFAULT_MEMORY,
        workers: int | None = None,
    ) -> tuple[ExecResult, ...]:
        """Run every program, at most `workers` alive at once.

        There is one result per program, in submission order whatever order
        they finish in. `workers` defaults to the core count, capped at 32.
        Arguments are checked before any program runs.
        """
        resolved = _run.check_arguments(dialect, timeout, memory)
        live = _check_workers(workers)
        texts = tuple(programs)
        for text in texts:
            if not isinstance(text, str):
                raise TypeError(f"program must be text, got {type(text).__name__}")
        zygote = self._live_zygote()
        with ThreadPoolExecutor(max_workers=min(live, max(1, len(texts)))) as pool:
            futures = [
                pool.submit(_run.run_program, zygote, t, resolved, timeout=timeout, memory=memory)
                for t in texts
            ]
            return tuple(f.result() for f in futures)

    def close(self) -> None:
        """Stop the zygote. Programs already forked keep their deadlines."""
        with self._lock:
            self._closed = True
            zygote, self._zygote = self._zygote, None
        if zygote is not None:
            zygote.close()

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


_default: Sandbox | None = None
_default_lock = threading.Lock()


def default_sandbox() -> Sandbox:
    """The process's shared sandbox, created on first use."""
    global _default
    with _default_lock:
        if _default is None:
            _default = Sandbox()
        return _default


def run(
    program: str,
    *,
    dialect: Dialect | str = Dialect.ARRIS,
    timeout: float = _run.DEFAULT_TIMEOUT,
    memory: int = _run.DEFAULT_MEMORY,
) -> ExecResult:
    """Run one program alone in a sandbox and say how it ended.

    Whatever the program does (a syntax error, an infinite loop, `os._exit`,
    a fork bomb) comes back as an `ExecResult` with a `Status`; only a
    caller's mistake raises: `ValueError` for an unknown dialect, a
    `timeout` that is not a positive finite number of seconds or a `memory`
    that is not a positive number of bytes, and `SandboxUnavailable` where
    this machine cannot isolate a program.

    The program binds a module-level `result` to an `arris.build.Solid`; it
    runs on a fresh model in a worker of its own, `timeout` seconds of wall
    clock and `memory` bytes of address space at most.

    >>> import arris_gym as ag
    >>> ok = ag.run("import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    >>> ok.status is ag.Status.OK
    True
    >>> ok.measures is not None and round(ok.measures.volume, 6)
    6.0
    >>> ag.run("result = (").status is ag.Status.SYNTAX
    True
    """
    return default_sandbox().run(program, dialect=dialect, timeout=timeout, memory=memory)


def run_many(
    programs: Iterable[str],
    *,
    dialect: Dialect | str = Dialect.ARRIS,
    timeout: float = _run.DEFAULT_TIMEOUT,
    memory: int = _run.DEFAULT_MEMORY,
    workers: int | None = None,
) -> tuple[ExecResult, ...]:
    """Run every program in its own sandbox, results in submission order.

    At most `workers` programs are alive at once. See `Sandbox.run_many`.

    >>> import arris_gym as ag
    >>> [r.status.value for r in ag.run_many(["result = (", "x = 1"])]
    ['syntax', 'runtime']
    """
    return default_sandbox().run_many(
        programs, dialect=dialect, timeout=timeout, memory=memory, workers=workers
    )
