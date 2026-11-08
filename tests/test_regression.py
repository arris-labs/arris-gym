"""Regression fixtures (`tests/fixtures/regression/`): failures shrunk from a run.

Each asserts the desired result (`.agents/rules/gym.md` §Testing), in its
fixture's dialect. One still failing names why in `expected.json`'s `xfail`
and is a strict `xfail` failing on its assertion alone, so the fixing commit
has to lift it. A case whose outcome turned on scheduling is run several
times: one passing run would prove nothing.
"""

from __future__ import annotations

import pytest

import arris_gym as ag
import fixture_cases

CASES = fixture_cases.load("regression")
# Runs of each case: a failure that showed in 39 runs of 40 shows in one of
# these with a chance of about one minus 1e-8.
REPEATS = 5


def _param(case: fixture_cases.Case) -> object:
    """A case, marked strict `xfail` with its reason where `expected.json` names one."""
    reason = case.expected.get("xfail")
    if reason is None:
        return pytest.param(case, id=case.slug)
    return pytest.param(
        case,
        id=case.slug,
        marks=pytest.mark.xfail(reason=str(reason), raises=AssertionError, strict=True),
    )


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_a_regression_fixture_ends_as_expected_every_run(case: fixture_cases.Case) -> None:
    # A comment of its own makes each run distinct: none is a cache hit of another.
    programs = [f"{case.program}\n# {i}\n" for i in range(REPEATS)]
    dialect = str(case.expected["dialect"])
    with ag.Sandbox() as sandbox:
        results = [sandbox.run(program, dialect=dialect) for program in programs]
        assert sandbox.executions == REPEATS
    for i, result in enumerate(results):
        assert fixture_cases.check(result, case.expected) == [], (case.slug, i, result.message)
