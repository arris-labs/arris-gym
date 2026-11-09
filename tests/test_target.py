"""`read_target`: a STEP text read in a step worker, one status per text (ADR-0011).

Every STEP here is built by arris from a part of known shape, then edited by
hand where a case needs a fault: the expected values come from that
construction, never from `read_target`'s own output.
"""

from __future__ import annotations

import doctest
import hashlib
from collections.abc import Iterator

import arris
import arris.build as b
import pydantic
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
from arris_gym.sandbox import outcome
from arris_gym.sandbox._frame import StepFrame
from arris_gym.sandbox.outcome import TARGET_STATUSES

# Within `fixture_cases.DEFAULT_TOLERANCE`'s reasoning: the kernel rounds a
# sum in its last bits; far below any modelling error.
TOLERANCE = 1e-6
# A box from the origin to (1, 2, 3): volume 1·2·3, area 2(1·2 + 1·3 + 2·3).
BOX_HIGH = (1.0, 2.0, 3.0)
BOX_VOLUME = 6.0
BOX_AREA = 22.0
# One corner of the box, as `write_step` writes its point: moving it far off
# leaves the edges through it running backwards on their lines.
ORIGIN_POINT = "CARTESIAN_POINT('',(0.,0.,0.));"
FAR_POINT = "CARTESIAN_POINT('',(50.,50.,50.));"


def _box_step() -> str:
    box = b.Solid.box((0.0, 0.0, 0.0), BOX_HIGH)
    return box.model.write_step([box.body])


BOX_STEP = _box_step()
HEADER = BOX_STEP[: BOX_STEP.index("DATA;")]
TRAILER = "ENDSEC;\nEND-ISO-10303-21;\n"


def _two_boxes_step() -> str:
    """One file holding the box twice: two solids, by construction."""
    model = arris.Model()
    first = model.read_step(BOX_STEP).solids[0].body
    second = model.read_step(BOX_STEP).solids[0].body
    assert first is not None
    assert second is not None
    return model.write_step([first, second])


def _data_sha256(step: str) -> str:
    return hashlib.sha256(step[step.index("DATA;") :].encode()).hexdigest()


@pytest.fixture(scope="module")
def sandbox() -> Iterator[ag.Sandbox]:
    with ag.Sandbox() as shared:
        yield shared


def test_a_box_step_is_a_target_with_the_boxs_measures(sandbox: ag.Sandbox) -> None:
    target = ag.read_target(BOX_STEP, sandbox=sandbox)
    assert target.status is ag.Status.OK, target.message
    assert target.measures is not None
    assert target.body is not None
    assert target.measures.volume == pytest.approx(BOX_VOLUME, abs=TOLERANCE)
    assert target.measures.area == pytest.approx(BOX_AREA, abs=TOLERANCE)
    assert target.measures.faces == 6
    assert target.measures.shells == 1
    assert target.measures.genus == 0
    assert target.step_sha256 == _data_sha256(BOX_STEP)
    assert target.versions.arris == arris.__version__


def test_a_targets_body_bytes_repeat_across_runs() -> None:
    with ag.Sandbox() as first, ag.Sandbox() as second:
        one = first.read_target(BOX_STEP)
        two = second.read_target(BOX_STEP)
    assert one.body is not None
    assert two.body is not None
    assert one.body.data == two.body.data
    assert one == two


def test_a_targets_body_is_a_body_score_reads(sandbox: ag.Sandbox) -> None:
    target = ag.read_target(BOX_STEP, sandbox=sandbox)
    box = ag.run("import arris.build as b\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    assert target.body is not None
    s = ag.score(box, target.body, sandbox=sandbox)
    assert s.status is ag.Status.OK
    assert s.reward == 1.0


@pytest.mark.parametrize(
    "step",
    [
        pytest.param("hello world", id="garbage"),
        pytest.param("", id="empty"),
        pytest.param(BOX_STEP.replace("DATA;", "DATA;\0", 1), id="nul-byte"),
    ],
)
def test_a_file_the_kernel_cannot_parse_is_its_refusal(sandbox: ag.Sandbox, step: str) -> None:
    target = sandbox.read_target(step)
    assert target.status is ag.Status.ARRIS_REFUSAL
    assert target.refusal is not None
    assert target.refusal.kind == arris.StepParseError.__name__
    assert target.message == target.refusal.message
    assert target.body is None
    assert target.measures is None


def test_a_step_with_no_solid_is_runtime_naming_the_count(sandbox: ag.Sandbox) -> None:
    target = sandbox.read_target(HEADER + "DATA;\n" + TRAILER)
    assert target.status is ag.Status.RUNTIME
    assert target.message == "the STEP holds 0 solids; a target is exactly 1"
    assert target.body is None
    assert target.refusal is None


def test_a_step_with_two_solids_is_runtime_naming_the_count(sandbox: ag.Sandbox) -> None:
    target = sandbox.read_target(_two_boxes_step())
    assert target.status is ag.Status.RUNTIME
    assert target.message == "the STEP holds 2 solids; a target is exactly 1"


def test_a_solid_the_kernel_refuses_is_arris_refusal_in_its_words(sandbox: ag.Sandbox) -> None:
    assert BOX_STEP.count(ORIGIN_POINT) > 0
    # Every copy of the origin moves, the box's corner vertex among them.
    broken = BOX_STEP.replace(ORIGIN_POINT, FAR_POINT)
    want = arris.Model().read_step(broken).solids[0].refusal
    assert want is not None
    target = sandbox.read_target(broken)
    assert target.status is ag.Status.ARRIS_REFUSAL
    assert target.refusal == ag.ArrisRefusal(
        kind=want.kind, message=want.message, entities=(f"#{want.entity}",)
    )
    assert target.message == want.message


def test_text_the_kernel_cannot_take_is_runtime(sandbox: ag.Sandbox) -> None:
    target = sandbox.read_target("\ud800")
    assert target.status is ag.Status.RUNTIME
    assert target.message.startswith("UnicodeEncodeError")
    assert target.step_sha256 is None


def test_the_callers_mistakes_raise(sandbox: ag.Sandbox) -> None:
    with pytest.raises(TypeError):
        sandbox.read_target(BOX_STEP.encode())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timeout"):
        sandbox.read_target(BOX_STEP, timeout=0.0)
    with pytest.raises(ValueError, match="memory"):
        sandbox.read_target(BOX_STEP, memory=0)


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "syntax", "message": "m", "refusal": None, "body": None},
        {"status": "ok", "message": "", "refusal": None, "body": None},
        {"status": "runtime", "message": "m", "refusal": None, "body": "AA=="},
        {"status": "arris_refusal", "message": "m", "refusal": None, "body": None},
    ],
)
def test_a_step_frame_that_contradicts_its_status_is_refused(fields: dict[str, object]) -> None:
    with pytest.raises(pydantic.ValidationError):
        StepFrame.model_validate(fields)


def test_a_target_never_ends_as_only_a_program_can() -> None:
    assert ag.Status.SYNTAX not in TARGET_STATUSES
    assert ag.Status.UNSUPPORTED_API not in TARGET_STATUSES
    versions = ag.Versions(arris="0", numpy="0", arris_gym="0")
    with pytest.raises(pydantic.ValidationError):
        ag.TargetResult(
            status=ag.Status.SYNTAX,
            message="m",
            refusal=None,
            body=None,
            measures=None,
            violations=(),
            step_sha256=None,
            versions=versions,
        )


ANY_TEXT = st.text(alphabet=st.characters(exclude_categories=()), max_size=200)


# Arbitrary text, surrogates and NULs included, alone or inside a STEP's
# frame: `read_target` returns, and the kernel refuses it or the count
# does; it never crashes the worker.
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(text=ANY_TEXT, framed=st.booleans())
def test_read_target_never_raises_on_any_text(text: str, framed: bool) -> None:
    step = HEADER + "DATA;\n" + text + "\n" + TRAILER if framed else text
    target = ag.read_target(step, timeout=2.0)
    assert target.status in (ag.Status.ARRIS_REFUSAL, ag.Status.RUNTIME), target.message


def test_the_doctests_run() -> None:
    assert doctest.testmod(outcome).failed == 0
