"""M0's acceptance (docs/plans/m0-sandbox.md): the sandbox run end to end, offline.

One program per status, `timeout` included, the hostile ones contained, a
deadline that holds, a thousand programs in submission order with a cache that
answers the second run, and a `run` that raises on no text.
"""

from __future__ import annotations

import hashlib
import pathlib
import time

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases

CASES = fixture_cases.load("sandbox")
BY_SLUG = {c.slug: c for c in CASES}
CORPUS_SIZE = 1000
HOSTILE_EVERY = 10  # one program in ten is hostile


def test_the_fixtures_reach_every_status_each_as_expected() -> None:
    for case in CASES:
        assert fixture_cases.check(fixture_cases.run(case), case.expected) == [], case.slug
    assert {c.expected["status"] for c in CASES} == {s.value for s in ag.Status}


def test_the_hostile_fixtures_cost_one_runtime_status_each() -> None:
    hostile = [c for c in CASES if c.slug.startswith("hostile-")]
    assert {c.slug for c in hostile} == {
        "hostile-fork-bomb",
        "hostile-memory-1gib",
        "hostile-connect",
        "hostile-read-outside",
    }
    for case in hostile:
        result = ag.run(case.program)
        assert result.status is ag.Status.RUNTIME, case.slug
        assert result.message == case.expected["message"], case.slug


def test_a_file_made_outside_the_workers_reach_cannot_be_read(tmp_path: pathlib.Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("made outside the reach", encoding="utf-8")
    result = ag.run(f"open({str(secret)!r}).read()\n")
    assert result.status is ag.Status.RUNTIME
    assert result.message.startswith("PermissionError")


def test_an_infinite_loop_times_out_within_two_seconds() -> None:
    start = time.monotonic()
    result = ag.run("while True:\n    pass\n", timeout=1.0)
    assert result.status is ag.Status.TIMEOUT
    assert time.monotonic() - start < 2.0


def _box(i: int) -> tuple[str, float]:
    a, b, c = 1 + i % 7, 1 + (i // 7) % 7, 1 + (i // 49) % 7
    program = f"import arris.build as b\nresult = b.Solid.box((0, 0, 0), ({a}, {b}, {c}))\n"
    return program, float(a * b * c)


# Hostile programs whose outcome is a function of the program alone, so the
# cache may keep them; the ones it never keeps (a crash, a timeout, a
# MemoryError) are in the next test.
HOSTILE = ("hostile-fork-bomb", "hostile-connect", "hostile-read-outside")
BENIGN = (
    "ok-box-with-hole",
    "syntax-unclosed",
    "runtime-raises",
    "runtime-no-result",
    "runtime-system-exit",
    "runtime-result-not-solid",
    "unsupported-api",
    "arris-refusal-fillet",
    "checker-fail-forged-vertex",
)


def _corpus() -> list[tuple[str, str, float | None]]:
    """(program, expected status, expected volume) for each of the thousand."""
    rows: list[tuple[str, str, float | None]] = []
    for i in range(CORPUS_SIZE):
        # A comment of its own makes every program distinct: no row is a cache hit of another.
        if i % HOSTILE_EVERY == HOSTILE_EVERY - 1:
            case = BY_SLUG[HOSTILE[(i // HOSTILE_EVERY) % len(HOSTILE)]]
            rows.append((f"{case.program}\n# {i}\n", str(case.expected["status"]), None))
        elif i % 3 == 0:
            case = BY_SLUG[BENIGN[(i // 3) % len(BENIGN)]]
            rows.append((f"{case.program}\n# {i}\n", str(case.expected["status"]), None))
        else:
            program, volume = _box(i)
            rows.append((f"{program}# {i}\n", "ok", volume))
    return rows


def test_a_thousand_programs_in_order_and_the_second_run_executes_none() -> None:
    corpus = _corpus()
    programs = [program for program, _, _ in corpus]
    assert len(set(programs)) == CORPUS_SIZE
    with ag.Sandbox() as sandbox:
        first = sandbox.run_many(programs, timeout=5.0)
        executed = sandbox.executions
        assert executed == CORPUS_SIZE
        second = sandbox.run_many(programs, timeout=5.0)
        assert sandbox.executions == executed
    assert len(first) == CORPUS_SIZE
    for i, (result, (program, status, volume)) in enumerate(zip(first, corpus, strict=True)):
        assert result.status.value == status, (i, result.message)
        assert result.program_sha256 == hashlib.sha256(program.encode()).hexdigest()
        if volume is not None:
            assert result.measures is not None
            assert fixture_cases.close(result.measures.volume, volume), i
    assert [r.model_dump() for r in second] == [r.model_dump() for r in first]
    assert ag.digest(second) == ag.digest(first)


def test_the_outcomes_a_cache_never_keeps_come_back_each_time() -> None:
    programs = [
        BY_SLUG["crash-segfault"].program,
        BY_SLUG["hostile-memory-1gib"].program,
        "while True:\n    pass\n",
    ]
    with ag.Sandbox() as sandbox:
        rows = sandbox.run_many(programs, timeout=1.0)
        assert [r.status.value for r in rows] == ["crash", "runtime", "timeout"]
        sandbox.run_many(programs, timeout=1.0)
        assert sandbox.executions == 2 * len(programs)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(alphabet=st.characters(exclude_categories=()), max_size=300))
def test_run_raises_on_no_drawn_text(text: str) -> None:
    assert isinstance(ag.run(text, timeout=2.0).status, ag.Status)
