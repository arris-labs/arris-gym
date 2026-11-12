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

from arris_gym.sandbox import _cache, _picture, _run, _target
from arris_gym.sandbox._zygote import Zygote
from arris_gym.sandbox.outcome import Dialect, ExecResult, TargetResult

# The most programs alive at once when the caller does not say: one per core,
# capped, since each live program holds up to `memory` bytes of address space.
DEFAULT_WORKERS_CAP = 32


def check_workers(workers: int | None) -> int:
    """The number of live forks `workers` asks for, or the caller's mistake."""
    if workers is None:
        return max(1, min(DEFAULT_WORKERS_CAP, os.cpu_count() or 1))
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError(f"workers must be a positive number, got {workers!r}")
    return workers


class Sandbox:
    """Runs programs, each alone in an isolated process.

    The zygote starts on first use and `close` stops it. Every method is
    safe to call from several threads at once. A result that is a function
    of the program, the dialect, `memory` and the pinned versions is cached,
    in memory or, given `cache_dir`, on disk; a `timeout`, a `crash` and a
    `MemoryError` never are. Like `arris_gym.run`, none
    raises on a program; a caller's mistake raises `ValueError` and a
    machine that cannot isolate a program raises `SandboxUnavailable`.

    >>> from arris_gym import Sandbox, Status
    >>> with Sandbox() as sandbox:
    ...     [r.status.value for r in sandbox.run_many(["result = (", "x = 1"])]
    ...     [r.status.value for r in sandbox.run_many(["result = ("])], sandbox.executions
    ['syntax', 'runtime']
    (['syntax'], 2)
    """

    def __init__(self, cache_dir: str | os.PathLike[str] | None = None) -> None:
        self._cache = _cache.Cache(cache_dir)
        self._executions = 0
        self._lock = threading.Lock()
        self._zygote: Zygote | None = None
        self._closed = False

    @property
    def executions(self) -> int:
        """How many programs this sandbox has actually executed.

        A run answered from the cache does not count.
        """
        with self._lock:
            return self._executions

    def _one(
        self, zygote: Zygote, program: str, dialect: Dialect, timeout: float, memory: int
    ) -> ExecResult:
        """One program: from the cache, or executed and, if it may be, stored."""
        key = _cache.cache_key(program, dialect, memory, _run.current_versions())
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        with self._lock:
            self._executions += 1
        executed = _run.run_program(zygote, program, dialect, timeout=timeout, memory=memory)
        if executed.cacheable:
            self._cache.put(key, executed.result)
        return executed.result

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
        return self._one(self._live_zygote(), program, resolved, timeout, memory)

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
        live = check_workers(workers)
        texts = tuple(programs)
        for text in texts:
            if not isinstance(text, str):
                raise TypeError(f"program must be text, got {type(text).__name__}")
        zygote = self._live_zygote()
        with ThreadPoolExecutor(max_workers=min(live, max(1, len(texts)))) as pool:
            futures = [pool.submit(self._one, zygote, t, resolved, timeout, memory) for t in texts]
            return tuple(f.result() for f in futures)

    def dump_png(
        self,
        result: ExecResult,
        path: str | os.PathLike[str],
        *,
        timeout: float = _run.DEFAULT_TIMEOUT,
        memory: int = _run.DEFAULT_MEMORY,
    ) -> None:
        """Write a picture of the result's body to `path`; see `arris_gym.dump_png`."""
        _run.check_arguments(Dialect.ARRIS, timeout, memory)
        _picture.draw(self._live_zygote(), result, path, timeout, memory)

    def read_target(
        self,
        step: str,
        *,
        timeout: float = _run.DEFAULT_TIMEOUT,
        memory: int = _run.DEFAULT_MEMORY,
    ) -> TargetResult:
        """Read one STEP text as a target; see `arris_gym.read_target`."""
        _run.check_arguments(Dialect.ARRIS, timeout, memory)
        if not isinstance(step, str):
            raise TypeError(f"step must be text, got {type(step).__name__}")
        return _target.read(self._live_zygote(), step, timeout=timeout, memory=memory)

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

    Under `dialect="arris"` the program binds a module-level `result` to an
    `arris.build.Solid`. Under `dialect="cq"` it imports `cadquery`, which is
    the subset `arris_gym.cq`, and its result is the last `show_object`
    argument, else module-level `result`, else `r`: a `Workplane` holding
    one solid. A present value is selected even when it is invalid. A call
    outside the subset ends `unsupported_api` naming it. The program runs on a fresh
    model in a worker of its own, `timeout` seconds of wall clock and
    `memory` bytes of address space at most.

    >>> import arris_gym as ag
    >>> ok = ag.run("import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    >>> ok.status is ag.Status.OK
    True
    >>> ok.measures is not None and round(ok.measures.volume, 6)
    6.0
    >>> ag.run("result = (").status is ag.Status.SYNTAX
    True
    >>> cq = "import cadquery as cq\\nshow_object(cq.Workplane('XY').sphere(1))"
    >>> sphere = ag.run(cq, dialect="cq")
    >>> sphere.status.value, sphere.message
    ('unsupported_api', 'Workplane.sphere')
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


def dump_png(
    result: ExecResult,
    path: str | os.PathLike[str],
    *,
    timeout: float = _run.DEFAULT_TIMEOUT,
    memory: int = _run.DEFAULT_MEMORY,
) -> None:
    """Write a picture of a result's body to the PNG file `path`.

    The body is tessellated by arris in a worker of its own, under the same
    limits as a program, and drawn by a `numpy` z-buffer as one 512 x 512
    greyscale sheet of four fixed orthographic views: front, right, top and
    an oblique one, each fitted to the part. It is for looking at, never for
    testing. Raises `ValueError` for a result with no body (its status is
    not `ok` or `checker_fail`) and `RuntimeError` when the body cannot be
    tessellated in time, with the worker's own words.

    >>> import arris_gym as ag, tempfile, pathlib
    >>> ok = ag.run("import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    >>> with tempfile.TemporaryDirectory() as folder:
    ...     ag.dump_png(ok, pathlib.Path(folder) / "box.png")
    ...     (pathlib.Path(folder) / "box.png").read_bytes()[:4]
    b'\\x89PNG'
    """
    default_sandbox().dump_png(result, path, timeout=timeout, memory=memory)


def read_target(
    step: str,
    *,
    sandbox: Sandbox | None = None,
    timeout: float = _run.DEFAULT_TIMEOUT,
    memory: int = _run.DEFAULT_MEMORY,
) -> TargetResult:
    """Read a STEP text as a target: its one solid, checked and measured.

    The text is read by arris's `read_step` on a fresh model in a step
    worker of `sandbox` (the process's shared one by default), and the
    solid's bytes are checked and measured by a body worker, `timeout`
    seconds of wall clock and `memory` bytes of address space at most for
    both. A STEP is untrusted input, as a program is. Exactly one solid the
    kernel builds and the checker accepts is `ok`; zero or several solids are
    `runtime` naming the count; a file the kernel cannot parse, or a solid it
    refuses, is `arris_refusal` with its words; then `checker_fail`,
    `timeout` and `crash` as for a program. Never raises on the text; raises
    `TypeError` for a `step` that is not text, `ValueError` for a `timeout`
    or `memory` that is not positive, and `SandboxUnavailable` where this
    machine cannot isolate a worker.

    >>> import arris_gym as ag, arris.build as b
    >>> box = b.Solid.box((0, 0, 0), (1, 2, 3))
    >>> target = ag.read_target(box.model.write_step([box.body]))
    >>> target.status.value, target.measures is not None and round(target.measures.volume, 6)
    ('ok', 6.0)
    >>> ag.read_target("hello").refusal.kind
    'StepParseError'
    """
    chosen = default_sandbox() if sandbox is None else sandbox
    return chosen.read_target(step, timeout=timeout, memory=memory)
