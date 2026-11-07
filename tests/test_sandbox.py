"""`Sandbox`, `run_many`: ordering, bounded forks, threads, caller's mistakes."""

from __future__ import annotations

import doctest
import threading
import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _sandbox

CASES = fixture_cases.load("sandbox")
BY_SLUG = {c.slug: c for c in CASES}
SLEEP = "import time\ntime.sleep({s})\nresult = 1\n"


def test_run_many_gives_one_row_per_program_in_submission_order() -> None:
    slugs = ["ok-box", "syntax-unclosed", "runtime-raises", "ok-box-with-hole", "unsupported-api"]
    programs = [BY_SLUG[s].program for s in slugs]
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(programs, workers=3)
    assert len(results) == len(programs)
    for slug, result in zip(slugs, results, strict=True):
        assert fixture_cases.check(result, BY_SLUG[slug].expected) == []


def test_results_keep_submission_order_when_the_first_finishes_last() -> None:
    # The first program runs longest, so it finishes after all the others.
    programs = [SLEEP.format(s=1.0)] + ["result = ("] * 5
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(programs, workers=6)
    assert [r.status for r in results] == [ag.Status.RUNTIME] + [ag.Status.SYNTAX] * 5


def test_workers_bound_the_live_forks() -> None:
    # Four 0.5 s programs through two workers take two rounds, one through four takes one.
    # Distinct text, so that the cache does not answer the repeats.
    programs = [SLEEP.format(s=0.5) + f"# {i}\n" for i in range(4)]
    with ag.Sandbox() as sandbox:
        sandbox.run("result = (")  # start the zygote outside the timings
        start = time.monotonic()
        sandbox.run_many(programs, workers=2)
        two = time.monotonic() - start
        again = [p + "# again\n" for p in programs]
        start = time.monotonic()
        sandbox.run_many(again, workers=4)
        four = time.monotonic() - start
    assert two >= 1.0
    assert four < two


def test_run_many_of_nothing_is_empty() -> None:
    with ag.Sandbox() as sandbox:
        assert sandbox.run_many([]) == ()
        assert sandbox.run_many(iter(())) == ()


def test_run_is_safe_from_many_threads() -> None:
    program = BY_SLUG["ok-box"].program
    out: list[ag.ExecResult] = []

    def work() -> None:
        out.append(sandbox.run(program))

    with ag.Sandbox() as sandbox:
        threads = [threading.Thread(target=work) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert len(out) == 8
    assert {r.body for r in out} == {out[0].body}
    assert all(fixture_cases.check(r, BY_SLUG["ok-box"].expected) == [] for r in out)


def test_the_default_instance_is_one_and_lazy() -> None:
    assert _sandbox.default_sandbox() is _sandbox.default_sandbox()
    assert [r.status for r in ag.run_many(["result = (", "result = ("])] == [ag.Status.SYNTAX] * 2


def test_a_closed_sandbox_refuses_and_close_is_idempotent() -> None:
    sandbox = ag.Sandbox()
    sandbox.close()
    sandbox.close()
    with pytest.raises(RuntimeError, match="closed"):
        sandbox.run("result = (")


def test_a_sandbox_never_used_starts_nothing() -> None:
    sandbox = ag.Sandbox()
    assert sandbox._zygote is None
    sandbox.close()


@pytest.mark.parametrize(
    "kwargs",
    [{"workers": 0}, {"workers": -1}, {"workers": True}, {"timeout": 0.0}, {"dialect": "cq"}],
)
def test_run_many_checks_its_arguments_before_running_anything(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match=r"workers|timeout|dialect"):
        ag.run_many(["result = ("], **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [b"result = 1", None, 3])
def test_a_program_that_is_not_text_is_the_callers_mistake(bad: object) -> None:
    with pytest.raises(TypeError, match="text"):
        ag.run(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="text"):
        ag.run_many(["result = (", bad])  # type: ignore[list-item]


# Arbitrary text, surrogates and NULs included: `run` returns, never raises.
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(st.text(alphabet=st.characters(exclude_categories=()), max_size=200))
def test_run_never_raises_on_any_text(text: str) -> None:
    result = ag.run(text, timeout=2.0)
    assert isinstance(result.status, ag.Status)


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(_sandbox).failed == 0
