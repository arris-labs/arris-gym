"""`rescore`: one row per entry, a failure counted under its stage (plans/m5-rescore step 5).

Programs and STEPs are built from parts of known shape, so a part scored
against itself has reward 1.0 by construction, never by `rescore`'s output.
"""

from __future__ import annotations

import doctest
from collections.abc import Iterator

import arris.build as b
import pytest

import arris_gym as ag
from arris_gym import rescore as rescore_package
from arris_gym.rescore import RescoreEntry, Stage, rescore
from arris_gym.rescore import _rescore as module
from arris_gym.reward import Score, failed_score
from arris_gym.sandbox import Dialect, Status

BOX = "import arris.build as b\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))"
FLAT_BOX = "import arris.build as b\nresult = b.Solid.box((0, 0, 0), (0, 0, 0))"
_box = b.Solid.box((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
BOX_STEP = _box.model.write_step([_box.body])


def entry(name: str, program: str = BOX, step: str = BOX_STEP) -> RescoreEntry:
    return RescoreEntry(
        name=name,
        source="test",
        licence="CC0-1.0",
        program=program,
        dialect=Dialect.ARRIS,
        step=step,
    )


@pytest.fixture(scope="module")
def sandbox() -> Iterator[ag.Sandbox]:
    with ag.Sandbox() as shared:
        yield shared


def test_a_part_against_itself_scores_one(sandbox: ag.Sandbox) -> None:
    table = rescore([entry("a")], sandbox=sandbox)
    (row,) = table.rows
    assert row.stage is Stage.NONE
    assert row.score.status is Status.OK
    assert row.score.reward == 1.0
    assert row.candidate_sha256 is not None  # a STEP round trip may change the bytes, not the part
    assert row.step_sha256 is not None
    assert row.source == "test"
    assert row.licence == "CC0-1.0"
    assert table.mean_reward == table.mean_reward_valid == 1.0


def test_a_refusal_is_the_programs_stage_with_the_kernels_words(sandbox: ag.Sandbox) -> None:
    (row,) = rescore([entry("a", FLAT_BOX)], sandbox=sandbox).rows
    assert row.stage is Stage.PROGRAM
    assert row.program_status is Status.ARRIS_REFUSAL
    assert row.program_refusal is not None
    assert row.program_refusal.kind == "OpDegenerateError"
    assert row.score.status is Status.ARRIS_REFUSAL
    assert row.score.reward == -0.5
    assert row.score.message == row.program_refusal.message
    assert row.target_sha256 is not None  # the target was read all the same


def test_a_target_that_fails_is_the_targets_stage_and_never_pays(sandbox: ag.Sandbox) -> None:
    (row,) = rescore([entry("a", step="not a step file")], sandbox=sandbox).rows
    assert row.stage is Stage.TARGET
    assert row.program_status is Status.OK
    assert row.candidate_sha256 is not None
    assert row.target_sha256 is None
    assert row.score.status is Status.RUNTIME
    assert row.score.reward == -1.0
    assert row.score.message  # the kernel's words, not empty


def test_a_program_failing_beside_a_target_failing_is_the_programs(sandbox: ag.Sandbox) -> None:
    (row,) = rescore([entry("a", "result = (", step="")], sandbox=sandbox).rows
    assert row.stage is Stage.PROGRAM
    assert row.score.status is Status.SYNTAX


def test_a_scoring_failure_is_the_scoring_stage(
    sandbox: ag.Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(result: ag.ExecResult, target: ag.BodyRef, **_: object) -> Score:
        return failed_score(Status.TIMEOUT, "scoring took 30.0 s")

    monkeypatch.setattr(module, "score", failing)
    table = rescore([entry("a")], sandbox=sandbox)
    (row,) = table.rows
    assert row.stage is Stage.SCORING
    assert row.score.status is Status.TIMEOUT
    assert row.score.reward == -1.0
    assert row.candidate_sha256 is not None
    assert row.target_sha256 is not None
    assert [(t.name, t.stage) for t in table.timed_out] == [("a", Stage.SCORING)]


def test_every_entry_has_a_row_and_the_table_ignores_order_and_workers(
    sandbox: ag.Sandbox,
) -> None:
    entries = [
        entry("d"),
        entry("a", FLAT_BOX),
        entry("c", "result = ("),
        entry("b", step="garbage"),
    ]
    table = rescore(entries, sandbox=sandbox, workers=1)
    assert table.programs == 4
    assert table.stages == {"none": 1, "program": 2, "target": 1, "scoring": 0}
    assert table.invalidity_rate == 0.75
    assert table.mean_reward == (1.0 - 0.5 - 1.0 - 1.0) / 4
    assert table.mean_reward_valid == 1.0
    assert rescore(entries[::-1], sandbox=sandbox, workers=4).digest == table.digest


def test_the_callers_mistakes_raise(sandbox: ag.Sandbox) -> None:
    with pytest.raises(ValueError, match="at least one row"):
        rescore([], sandbox=sandbox)
    with pytest.raises(ValueError, match="twice"):
        rescore([entry("a"), entry("a")], sandbox=sandbox)
    with pytest.raises(ValueError, match="workers"):
        rescore([entry("a")], sandbox=sandbox, workers=0)


def test_without_a_sandbox_it_makes_and_closes_its_own() -> None:
    assert rescore([entry("a")]).mean_reward == 1.0


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(module).failed == 0
    assert rescore_package.rescore is rescore
