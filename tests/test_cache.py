"""The cache: a second run executes nothing, and only a function of the key is kept."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Callable

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _cache, _run

CASES = {c.slug: c for c in fixture_cases.load("sandbox")}
SLUGS = ["ok-box", "ok-box-with-hole", "syntax-unclosed", "runtime-raises", "arris-refusal-fillet"]
PROGRAMS = [CASES[s].program for s in SLUGS]
ALLOCATE = "x = bytearray(2 * 2**30)\nresult = 1\n"
CATCH_MEMORY_ERROR = (
    "try:\n    bytearray(2 * 2**30)\n"
    "except MemoryError:\n    raise MemoryError('caught and reraised')\n"
)


@pytest.mark.parametrize("on_disk", [False, True], ids=["memory", "disk"])
def test_a_second_run_makes_no_executions_and_returns_equal_rows(
    tmp_path: pathlib.Path, on_disk: bool
) -> None:
    with ag.Sandbox(cache_dir=tmp_path / "cache" if on_disk else None) as sandbox:
        first = sandbox.run_many(PROGRAMS)
        assert sandbox.executions == len(PROGRAMS)
        second = sandbox.run_many(PROGRAMS)
        assert sandbox.executions == len(PROGRAMS)
        assert second == first
        assert sandbox.run(PROGRAMS[0]) == first[0]
        assert sandbox.executions == len(PROGRAMS)


def test_a_disk_cache_serves_a_new_sandbox(tmp_path: pathlib.Path) -> None:
    with ag.Sandbox(cache_dir=tmp_path) as first:
        rows = first.run_many(PROGRAMS)
    with ag.Sandbox(cache_dir=tmp_path) as second:
        assert second.run_many(PROGRAMS) == rows
        assert second.executions == 0
    assert rows[0].body is not None
    assert rows[0].measures is not None


def test_a_changed_memory_limit_misses() -> None:
    with ag.Sandbox() as sandbox:
        sandbox.run(PROGRAMS[0])
        sandbox.run(PROGRAMS[0], memory=256 * 2**20)
        assert sandbox.executions == 2
        sandbox.run(PROGRAMS[0], memory=256 * 2**20)
        assert sandbox.executions == 2


def test_the_key_moves_with_each_thing_that_decides_a_result() -> None:
    v = _run.current_versions()
    base = _cache.cache_key("x", ag.Dialect.ARRIS, 1, v)
    assert base == _cache.cache_key("x", ag.Dialect.ARRIS, 1, v)
    assert base != _cache.cache_key("y", ag.Dialect.ARRIS, 1, v)
    assert base != _cache.cache_key("x", ag.Dialect.ARRIS, 2, v)
    assert base != _cache.cache_key("x", ag.Dialect.ARRIS, 1, v.model_copy(update={"arris": "0"}))
    assert base != _cache.cache_key("x", ag.Dialect.ARRIS, 1, v.model_copy(update={"numpy": "0"}))
    other = v.model_copy(update={"arris_gym": "0"})
    assert base != _cache.cache_key("x", ag.Dialect.ARRIS, 1, other)


@pytest.mark.parametrize(
    ("program", "timeout", "status"),
    [
        ("while True:\n    pass\n", 0.5, ag.Status.TIMEOUT),
        ("import os\nos._exit(3)\n", 5.0, ag.Status.CRASH),
        (ALLOCATE, 5.0, ag.Status.RUNTIME),
        (CATCH_MEMORY_ERROR, 5.0, ag.Status.RUNTIME),
    ],
    ids=["timeout", "crash", "memory-error", "reraised-memory-error"],
)
def test_an_outcome_the_machine_decides_runs_again(
    program: str, timeout: float, status: ag.Status
) -> None:
    with ag.Sandbox() as sandbox:
        first = sandbox.run(program, timeout=timeout, memory=512 * 2**20)
        assert first.status is status
        sandbox.run(program, timeout=timeout, memory=512 * 2**20)
        assert sandbox.executions == 2


def test_a_torn_entry_is_a_miss(tmp_path: pathlib.Path) -> None:
    program = PROGRAMS[0]
    key = _cache.cache_key(program, ag.Dialect.ARRIS, _run.DEFAULT_MEMORY, _run.current_versions())
    entry = tmp_path / key[:2] / f"{key}.json"
    body = tmp_path / key[:2] / f"{key}.body"
    damages: dict[str, Callable[[], object]] = {
        "json-cut": lambda: entry.write_bytes(entry.read_bytes()[:40]),
        "json-empty": lambda: entry.write_bytes(b""),
        "json-wrong-shape": lambda: entry.write_text(json.dumps({"result": {}})),
        "body-missing": lambda: body.unlink(),
        "body-flipped": lambda: body.write_bytes(b"\x00" + body.read_bytes()[1:]),
    }
    with ag.Sandbox(cache_dir=tmp_path) as sandbox:
        good = sandbox.run(program)
        for damage in damages.values():
            damage()
            again = sandbox.run(program)
            assert again.status is good.status
            assert again.body == good.body
        assert sandbox.executions == 1 + len(damages)
        sandbox.run(program)  # the last run repaired the entry
        assert sandbox.executions == 1 + len(damages)


def test_a_cache_directory_holds_only_complete_files(tmp_path: pathlib.Path) -> None:
    with ag.Sandbox(cache_dir=tmp_path) as sandbox:
        sandbox.run_many(PROGRAMS)
    names = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert names
    assert not [n for n in names if n.endswith(".tmp")]


def test_the_fixtures_survive_the_cache(tmp_path: pathlib.Path) -> None:
    with ag.Sandbox(cache_dir=tmp_path) as sandbox:
        for _ in range(2):
            for slug in SLUGS:
                result = sandbox.run(CASES[slug].program)
                assert fixture_cases.check(result, CASES[slug].expected) == []
