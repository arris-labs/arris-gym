"""Corpus aggregates over scores: every row counted, the denominator stated.

docs/ARCHITECTURE.md §The reward, `.agents/rules/gym.md` ("failures are
counted, never dropped").
"""

from __future__ import annotations

from collections.abc import Iterable

from arris_gym.reward._score import Score
from arris_gym.sandbox.outcome import Status


def invalidity_rate(scores: Iterable[Score]) -> float:
    """The share of all `scores` that are not `ok`: BenchCAD's invalidity rate.

    The denominator is every row given, the failures included; a score is
    valid only when its status is `ok`, so a program that did not run, ended
    `arris_refusal`, `checker_fail` or any other failure, and a valid program
    whose scoring itself ended `crash`, `timeout` or `runtime`, are all
    invalid. Raises `ValueError` for no scores, since a rate over nothing has
    no value (never a silent 0).

    >>> from arris_gym import run, score
    >>> box = "import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 1, 1))"
    >>> target = run(box)
    >>> assert target.body is not None
    >>> rows = [score(run(text), target.body) for text in ("result = (", box)]
    >>> invalidity_rate(rows)
    0.5
    """
    rows = list(scores)
    if not rows:
        raise ValueError("invalidity_rate of no scores has no value")
    invalid = sum(1 for row in rows if row.status is not Status.OK)
    return invalid / len(rows)
