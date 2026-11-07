"""Regression fixtures (`tests/fixtures/regression/`): failures shrunk from a run.

Each asserts the desired result (`.agents/rules/gym.md` §Testing). A case
whose outcome turned on scheduling is run several times: one passing run
would prove nothing.
"""

from __future__ import annotations

import pytest

import arris_gym as ag
import fixture_cases

CASES = fixture_cases.load("regression")
# Runs of each case: a failure that showed in 39 runs of 40 shows in one of
# these with a chance of about one minus 1e-8.
REPEATS = 5


@pytest.mark.parametrize("case", CASES, ids=[c.slug for c in CASES])
def test_a_regression_fixture_ends_as_expected_every_run(case: fixture_cases.Case) -> None:
    # A comment of its own makes each run distinct: none is a cache hit of another.
    programs = [f"{case.program}\n# {i}\n" for i in range(REPEATS)]
    with ag.Sandbox() as sandbox:
        results = [sandbox.run(program) for program in programs]
        assert sandbox.executions == REPEATS
    for i, result in enumerate(results):
        assert fixture_cases.check(result, case.expected) == [], (case.slug, i, result.message)
