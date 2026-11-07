"""The result cache: an exact function of what decides a result.

The key is the hash of the program's bytes, the dialect, the memory limit,
the process limit and the pinned versions: a program can catch `MemoryError`
and go on, so the limits are part of what it computes. `timeout` is not:
a result that depends on it is never stored. arris-gym's version stands for
`cq`'s until they split. On disk an entry is one JSON file (the result without
its body) and one body file, both by key, each written to a temporary name
and renamed; the JSON is renamed last, so an entry without it does not exist.
Nothing here is reachable by a worker, whose filesystem is read-only and
whose Landlock domain does not list the cache directory. Private.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import threading
import uuid

from arris_gym.sandbox import _isolate
from arris_gym.sandbox.outcome import BodyRef, Dialect, ExecResult, Versions


def cache_key(program: str, dialect: Dialect, memory: int, versions: Versions) -> str:
    """The hex key of a run: what decides its result, and nothing else."""
    from arris_gym.sandbox._program import TEXT_ERRORS

    fields = {
        "program_sha256": hashlib.sha256(program.encode("utf-8", TEXT_ERRORS)).hexdigest(),
        "dialect": dialect.value,
        "memory": memory,
        "nproc": _isolate.NPROC_LIMIT,
        "arris": versions.arris,
        "numpy": versions.numpy,
        "arris_gym": versions.arris_gym,
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


class Cache:
    """Results by key: in memory, or on disk under `directory`.

    Safe from several threads and processes: a write is a rename. A torn or
    unreadable entry (a missing body, a body whose SHA-256 differs, invalid
    JSON, a result that does not validate) is a miss, never an error.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self._directory = None if directory is None else pathlib.Path(directory)
        self._memory: dict[str, ExecResult] = {}
        self._lock = threading.Lock()
        if self._directory is not None:
            self._directory.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[pathlib.Path, pathlib.Path]:
        assert self._directory is not None
        folder = self._directory / key[:2]
        return folder / f"{key}.json", folder / f"{key}.body"

    def get(self, key: str) -> ExecResult | None:
        """The stored result for `key`, or None."""
        if self._directory is None:
            with self._lock:
                return self._memory.get(key)
        entry, body_file = self._paths(key)
        try:
            stored = json.loads(entry.read_text(encoding="utf-8"))
            fields = dict(stored["result"])
            sha = stored["body_sha256"]
            if sha is not None:
                body = body_file.read_bytes()
                if hashlib.sha256(body).hexdigest() != sha:
                    return None
                fields["body"] = BodyRef.of(body)
            else:
                fields["body"] = None
            return ExecResult.model_validate(fields)
        except (OSError, ValueError, KeyError, TypeError):
            return None  # pydantic's ValidationError is a ValueError

    def put(self, key: str, result: ExecResult) -> None:
        """Store `result` under `key`. The caller has decided it is cacheable."""
        if self._directory is None:
            with self._lock:
                self._memory[key] = result
            return
        entry, body_file = self._paths(key)
        entry.parent.mkdir(parents=True, exist_ok=True)
        sha = None
        if result.body is not None:
            sha = result.body.sha256
            _write_atomic(body_file, result.body.data)
        stored = {
            "result": json.loads(result.model_dump_json(exclude={"body"})),
            "body_sha256": sha,
        }
        _write_atomic(entry, json.dumps(stored, sort_keys=True).encode("utf-8"))


def _write_atomic(path: pathlib.Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
