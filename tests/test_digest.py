"""`dump_text` and `digest`: equal where the results are equal, moved by any change."""

from __future__ import annotations

import doctest
import hashlib
import math
import pathlib

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _digest

CASES = {c.slug: c for c in fixture_cases.load("sandbox")}
SLUGS = ["ok-box", "ok-box-with-hole", "syntax-unclosed", "runtime-raises", "arris-refusal-fillet"]
PROGRAMS = [CASES[s].program for s in SLUGS]
GOLDEN = pathlib.Path(__file__).parent / "fixtures" / "dump" / "arris-refusal-fillet.txt"


def refusal_result(message: str | None = None) -> ag.ExecResult:
    """The fillet fixture's refusal, built by hand from its expectation."""
    expected = CASES["arris-refusal-fillet"].expected
    refusal = expected["refusal"]
    assert isinstance(refusal, dict)
    text = refusal["message"] if message is None else message
    return ag.ExecResult(
        status=ag.Status.ARRIS_REFUSAL,
        message=text,
        refusal=ag.ArrisRefusal(kind=refusal["kind"], message=text, entities=("+e0", "+f2")),
        body=None,
        measures=None,
        violations=(),
        program_sha256=hashlib.sha256(CASES["arris-refusal-fillet"].program.encode()).hexdigest(),
        dialect=ag.Dialect.ARRIS,
        versions=ag.Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0"),
        seconds=0.123,
    )


def test_a_refusals_text_is_the_committed_golden() -> None:
    assert ag.dump_text(refusal_result()) == GOLDEN.read_text(encoding="utf-8")


def test_a_change_in_a_refusals_words_shows_in_the_text_and_moves_the_digest() -> None:
    changed = refusal_result(message="degenerate result: the blend leaves its face")
    before, after = ag.dump_text(refusal_result()), ag.dump_text(changed)
    assert before != after
    assert ag.digest([refusal_result()]) != ag.digest([changed])


def test_seconds_are_outside_text_and_digest() -> None:
    slow = refusal_result().model_copy(update={"seconds": 99.0})
    assert ag.dump_text(slow) == ag.dump_text(refusal_result())
    assert ag.digest([slow]) == ag.digest([refusal_result()])


def test_digest_is_equal_across_workers_and_zygotes() -> None:
    with ag.Sandbox() as one, ag.Sandbox() as other:
        serial = one.run_many(PROGRAMS, workers=1)
        wide = other.run_many(PROGRAMS, workers=5)
    assert ag.digest(serial) == ag.digest(wide)
    assert [ag.dump_text(r) for r in serial] == [ag.dump_text(r) for r in wide]


def test_digest_follows_program_order() -> None:
    rows = ag.run_many(PROGRAMS)
    assert ag.digest(rows) != ag.digest(rows[::-1])
    assert ag.digest(rows[:-1]) != ag.digest(rows)
    assert ag.digest([]) == hashlib.sha256().hexdigest()


def test_a_one_bit_change_of_a_measure_moves_the_digest() -> None:
    (box,) = ag.run_many([CASES["ok-box"].program])
    assert box.measures is not None
    volume = math.nextafter(box.measures.volume, math.inf)
    assert volume != box.measures.volume
    nudged = box.model_copy(update={"measures": box.measures.model_copy(update={"volume": volume})})
    assert ag.digest([nudged]) != ag.digest([box])
    # `repr` is the shortest string that reads back exactly, so the text moves too.
    assert ag.dump_text(nudged) != ag.dump_text(box)


@pytest.mark.parametrize("slug", SLUGS)
def test_text_is_stable_for_each_status(slug: str) -> None:
    result = ag.run(CASES[slug].program)
    text = ag.dump_text(result)
    assert text.startswith(f"status: {result.status.value}\n")
    assert text == ag.dump_text(ag.run(CASES[slug].program))
    assert ("measures.volume" in text) == (result.measures is not None)


def test_an_ok_texts_floats_are_readable() -> None:
    (box,) = ag.run_many([CASES["ok-box"].program])
    assert box.measures is not None
    assert f"measures.volume: {box.measures.volume!r}\n" in ag.dump_text(box)
    assert "0x" not in ag.dump_text(box)


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(_digest).failed == 0
