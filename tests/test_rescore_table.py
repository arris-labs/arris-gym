"""The re-scored table (plans/m5-rescore step 4): counts over all rows, the digest.

Rows are built by hand, so every expected count and mean is from how they were
written, never from the table's own output.
"""

from __future__ import annotations

import doctest
import hashlib
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from arris_gym.rescore import RescoreEntry, RescoreRow, RescoreTable, Stage, _table
from arris_gym.reward import DEFAULT_REWARD, FieldMetrics, IouRoute, Score
from arris_gym.sandbox.outcome import ArrisRefusal, Dialect, Status, Versions

VERSIONS = Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def failed(status: Status, reward: float, message: str = "m") -> Score:
    return Score(
        status=status,
        message=message,
        reward=reward,
        iou=None,
        iou_route=None,
        surface=None,
        measures=None,
        topology=None,
        field=None,
        reward_version=DEFAULT_REWARD.version,
        versions=VERSIONS,
    )


def good(reward: float, route: IouRoute = IouRoute.EXACT) -> Score:
    return Score(
        status=Status.OK,
        message="",
        reward=reward,
        iou=1.0,
        iou_route=route,
        surface=1.0,
        measures=1.0,
        topology=1.0,
        field=FieldMetrics(voxel_iou_64=1.0, chamfer_x1000=0.0),
        reward_version=DEFAULT_REWARD.version,
        versions=VERSIONS,
    )


def row(name: str, stage: Stage, score: Score, **kw: object) -> RescoreRow:
    ok = stage in (Stage.NONE, Stage.TARGET, Stage.SCORING)
    refusal = ArrisRefusal(kind="OpDegenerateError", message="x", entities=())
    fields: dict[str, object] = {
        "name": name,
        "source": "BenchCAD/BenchCAD",
        "licence": "CC-BY-4.0",
        "program_sha256": sha("p" + name),
        "dialect": Dialect.CQ,
        "stage": stage,
        "program_status": Status.OK if ok else score.status,
        "program_refusal": None
        if ok
        else (refusal if score.status is Status.ARRIS_REFUSAL else None),
        "candidate_sha256": sha("c" + name) if ok else None,
        "target_sha256": sha("t" + name) if stage in (Stage.NONE, Stage.SCORING) else None,
        "step_sha256": sha("s" + name),
        "score": score,
        "versions": VERSIONS,
    }
    fields.update(kw)
    return RescoreRow(**fields)  # type: ignore[arg-type]


ROWS = [
    row("d", Stage.NONE, good(1.0)),
    row("a", Stage.NONE, good(0.5, IouRoute.SAMPLED)),
    row("c", Stage.PROGRAM, failed(Status.ARRIS_REFUSAL, -0.5)),
    row("b", Stage.PROGRAM, failed(Status.TIMEOUT, -1.0, "took 30.1 s")),
    row("e", Stage.TARGET, failed(Status.RUNTIME, -1.0)),
    row("f", Stage.SCORING, failed(Status.CRASH, -1.0)),
]


def test_counts_cover_every_row_and_every_name_with_zeros() -> None:
    table = RescoreTable.of(ROWS)
    assert [r.name for r in table.rows] == list("abcdef")
    assert table.programs == 6
    assert table.statuses == {
        "ok": 2,
        "syntax": 0,
        "runtime": 1,
        "unsupported_api": 0,
        "arris_refusal": 1,
        "checker_fail": 0,
        "timeout": 1,
        "crash": 1,
    }
    assert table.stages == {"none": 2, "program": 2, "target": 1, "scoring": 1}
    assert table.iou_routes == {"exact": 1, "sampled": 1}
    assert table.invalidity_rate == 4 / 6
    assert [(t.name, t.stage) for t in table.timed_out] == [("b", Stage.PROGRAM)]


def test_the_means_are_over_all_rows_and_the_survivors_beside_it() -> None:
    table = RescoreTable.of(ROWS)
    # (1.0 + 0.5 - 0.5 - 1.0 - 1.0 - 1.0) / 6 by hand; the survivors' (1.0 + 0.5) / 2.
    assert table.mean_reward == -2.0 / 6
    assert table.valid == 2
    assert table.mean_reward_valid == 0.75


def test_no_valid_row_has_no_survivor_mean() -> None:
    table = RescoreTable.of([ROWS[2]])
    assert table.valid == 0
    assert table.mean_reward_valid is None
    assert table.mean_reward == -0.5


def test_mean_is_summed_exactly() -> None:
    rows = [row(f"r{i}", Stage.NONE, good(0.1 + i * 1e-9)) for i in range(5)]
    table = RescoreTable.of(rows)
    assert table.mean_reward == math.fsum(0.1 + i * 1e-9 for i in range(5)) / 5


def test_the_digest_ignores_a_timeouts_message_and_notices_a_score() -> None:
    base = RescoreTable.of(ROWS).digest
    other = [*ROWS[:3], row("b", Stage.PROGRAM, failed(Status.TIMEOUT, -1.0, "took 99 s"))]
    assert RescoreTable.of([*other, *ROWS[4:]]).digest == base
    moved = [row("a", Stage.NONE, good(0.6, IouRoute.SAMPLED)), *ROWS[0:1], *ROWS[2:]]
    assert RescoreTable.of(moved).digest != base


def test_the_digest_notices_a_stage() -> None:
    retargeted = [
        *ROWS[:4],
        row("e", Stage.SCORING, failed(Status.RUNTIME, -1.0), target_sha256=sha("tt")),
    ]
    assert RescoreTable.of(retargeted).digest != RescoreTable.of(ROWS[:5]).digest


@given(st.permutations(ROWS))
def test_a_permutation_does_not_move_the_digest(order: list[RescoreRow]) -> None:
    assert RescoreTable.of(order) == RescoreTable.of(ROWS)
    assert RescoreTable.of(order).digest == RescoreTable.of(ROWS).digest


def test_json_round_trips_and_markdown_names_the_denominators() -> None:
    table = RescoreTable.of(ROWS)
    assert RescoreTable.from_json(table.to_json()) == table
    markdown = table.to_markdown()
    assert table.digest in markdown
    assert f"over all {len(ROWS)} programs" in markdown
    assert "survivors" in markdown
    assert markdown.count("\n| ") == len(ROWS) + 1


def test_a_table_whose_digest_or_counts_disagree_is_refused() -> None:
    table = RescoreTable.of(ROWS)
    fields = table.model_dump()
    fields["rows"] = table.rows
    fields["timed_out"] = table.timed_out
    for key, bad in (
        ("digest", sha("x")),
        ("programs", 5),
        ("mean_reward", 0.0),
        ("invalidity_rate", 0.0),
        ("statuses", {**table.statuses, "ok": 3}),
        ("stages", {**table.stages, "none": 3}),
        ("iou_routes", {"exact": 2, "sampled": 0}),
        ("valid", 3),
        ("mean_reward_valid", 1.0),
        ("timed_out", ()),
    ):
        with pytest.raises(ValidationError, match="disagrees"):
            RescoreTable(**{**fields, key: bad})


def test_a_table_refuses_no_rows_unsorted_rows_and_a_repeated_name() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        RescoreTable.of([])
    with pytest.raises(ValidationError, match="sorted"):
        RescoreTable(**{**RescoreTable.of(ROWS).model_dump(), "rows": tuple(ROWS)})
    with pytest.raises(ValueError, match="sorted by name, each name once"):
        RescoreTable.of([ROWS[0], ROWS[0]])


def test_a_row_refuses_a_stage_its_score_contradicts() -> None:
    with pytest.raises(ValidationError, match="stage none"):
        row("x", Stage.NONE, failed(Status.RUNTIME, -1.0), program_status=Status.OK)
    with pytest.raises(ValidationError, match="stage program"):
        row("x", Stage.PROGRAM, good(1.0), program_status=Status.OK)
    with pytest.raises(ValidationError, match="stage target"):
        row("x", Stage.TARGET, good(1.0))
    with pytest.raises(ValidationError, match="stage scoring"):
        row("x", Stage.SCORING, failed(Status.RUNTIME, -1.0), program_status=Status.SYNTAX)
    with pytest.raises(ValidationError, match="both body digests"):
        row("x", Stage.NONE, good(1.0), target_sha256=None)
    with pytest.raises(ValidationError, match="candidate"):
        row("x", Stage.TARGET, failed(Status.RUNTIME, -1.0), candidate_sha256=None)


def test_a_row_refuses_a_refusal_without_its_status_and_a_bad_digest() -> None:
    refusal = ArrisRefusal(kind="K", message="m", entities=())
    with pytest.raises(ValidationError, match="program_refusal"):
        row("x", Stage.NONE, good(1.0), program_refusal=refusal)
    with pytest.raises(ValidationError, match="program_refusal"):
        row("x", Stage.PROGRAM, failed(Status.ARRIS_REFUSAL, -0.5), program_refusal=None)
    with pytest.raises(ValidationError, match="hex SHA-256"):
        row("x", Stage.NONE, good(1.0), step_sha256="abc")


def test_an_entry_has_a_name() -> None:
    entry = RescoreEntry(
        name="n", source="s", licence="l", program="p", dialect=Dialect.CQ, step="ISO;"
    )
    assert entry.name == "n"
    with pytest.raises(ValidationError, match="a name"):
        RescoreEntry(name="", source="s", licence="l", program="p", dialect=Dialect.CQ, step="")


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(_table).failed == 0
