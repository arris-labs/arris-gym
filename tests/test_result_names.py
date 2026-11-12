"""ADR-0015 selects by presence, identically under cq and the oracle."""

from collections.abc import Iterator

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
import oracle_run
from arris_gym.fidelity import OracleStatus, compare
from arris_gym.sandbox._zygote import Zygote

PREFIX = "import cadquery as cq\npart = cq.Workplane('XY').box(2, 4, 6)\n"
# Invalid higher-priority values must not fall through to a valid lower one.
ENDINGS = [
    ("r = part", True),
    ("r: object = part", True),
    ("r = part\npass", True),
    ("r = None", False),
    ("r = cq.Workplane('XY')", False),
    ("result = part\nr = None", True),
    ("r = None\nresult = part", True),
    ("result = None\nr = part", False),
    ("result = 0\nr = part", False),
    ("result = None\nr = part\ndel result", True),
    ("result = None\nr = None\nshow_object(part)", True),
    ("show_object(None)\nshow_object(part)\nresult = None\nr = None", True),
    ("show_object(part)\nshow_object(None)\nresult = part\nr = part", False),
    ("r = part\ndel r", False),
    ("def local():\n    r = part\nlocal()", False),
    ("another = part", False),
]
DIMENSIONS = st.tuples(*(st.integers(1, 20) for _ in range(3)))


@pytest.mark.parametrize(("ending", "valid"), ENDINGS)
def test_cq_selects_the_last_shown_value_then_result_then_r(ending: str, valid: bool) -> None:
    result = ag.run(PREFIX + ending, dialect="cq")
    assert result.status is (ag.Status.OK if valid else ag.Status.RUNTIME), result.message
    if valid:
        assert result.measures is not None
        assert fixture_cases.close(result.measures.volume, 48.0)


def test_result_precedes_r_even_when_both_are_solids() -> None:
    result = ag.run(PREFIX + "result = part\nr = cq.Workplane('XY').box(1, 1, 1)", dialect="cq")
    assert result.measures is not None
    assert fixture_cases.close(result.measures.volume, 48.0)


@settings(max_examples=25, deadline=None)
@given(DIMENSIONS)
def test_result_and_r_give_equal_cq_rows(dimensions: tuple[int, int, int]) -> None:
    expression = f"cq.Workplane('XY').box{dimensions!r}"
    with ag.Sandbox() as sandbox:
        rows = [
            sandbox.run(f"import cadquery as cq\n{name} = {expression}", dialect="cq")
            for name in ("result", "r")
        ]
    assert all(row.status is ag.Status.OK for row in rows)
    # Different source text necessarily has another hash; time is not a result.
    assert rows[0].model_dump(exclude={"program_sha256", "seconds"}) == rows[1].model_dump(
        exclude={"program_sha256", "seconds"}
    )


def test_arris_still_reads_only_the_module_level_result() -> None:
    prefix = "import arris.build as b\nr = b.Solid.box((0, 0, 0), (2, 4, 6))\n"
    with ag.Sandbox() as sandbox:
        missing = sandbox.run(prefix, dialect="arris")
        invalid = sandbox.run(prefix + "result = None", dialect="arris")
        valid = sandbox.run(prefix + "result = r\nr = None", dialect="arris")
    assert missing.status is ag.Status.RUNTIME
    assert missing.message == "the program ended without binding `result`"
    assert invalid.status is ag.Status.RUNTIME
    assert invalid.message == "`result` is of type NoneType, not arris.build.Solid"
    assert valid.status is ag.Status.OK
    assert valid.measures is not None
    assert fixture_cases.close(valid.measures.volume, 48.0)


@pytest.fixture(scope="module")
def oracle() -> Iterator[oracle_run.OracleZygote]:
    with Zygote() as zygote, oracle_run.OracleZygote(zygote, oracle_run.spec()) as handle:
        yield handle


@pytest.mark.oracle
@pytest.mark.parametrize(("ending", "valid"), ENDINGS)
def test_oracle_selects_the_same_value(
    oracle: oracle_run.OracleZygote, ending: str, valid: bool
) -> None:
    report = oracle_run.run_report(oracle, PREFIX + ending, timeout=oracle_run.DEFAULT_TIMEOUT)
    assert report.status is (OracleStatus.OK if valid else OracleStatus.NO_RESULT), report.message
    if valid:
        assert report.measures is not None
        assert fixture_cases.close(report.measures.volume, 48.0)


@pytest.mark.oracle
def test_oracle_result_precedes_r_even_when_both_are_solids(
    oracle: oracle_run.OracleZygote,
) -> None:
    program = PREFIX + "result = part\nr = cq.Workplane('XY').box(1, 1, 1)"
    report = oracle_run.run_report(oracle, program, timeout=oracle_run.DEFAULT_TIMEOUT)
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    assert fixture_cases.close(report.measures.volume, 48.0)


@pytest.mark.oracle
@settings(max_examples=20, deadline=None)
@given(dimensions=DIMENSIONS)
def test_result_and_r_give_equal_oracle_rows(
    oracle: oracle_run.OracleZygote, dimensions: tuple[int, int, int]
) -> None:
    expression = f"cq.Workplane('XY').box{dimensions!r}"
    rows = [
        oracle_run.run_report(
            oracle,
            f"import cadquery as cq\n{name} = {expression}",
            timeout=oracle_run.DEFAULT_TIMEOUT,
        )
        for name in ("result", "r")
    ]
    assert all(row.status is OracleStatus.OK for row in rows)
    assert rows[0].model_dump(exclude={"program_sha256", "seconds"}) == rows[1].model_dump(
        exclude={"program_sha256", "seconds"}
    )


@pytest.mark.oracle
def test_r_fixture_agrees_with_a_fresh_oracle_worker() -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == "ok-result-r")
    with Zygote() as zygote:
        outcome = oracle_run.run_one(
            zygote, oracle_run.spec(), case.program, timeout=oracle_run.DEFAULT_TIMEOUT
        )
    from arris_gym.fidelity import parse_outcome

    report = parse_outcome(outcome, case.program, timeout=oracle_run.DEFAULT_TIMEOUT, seconds=0.0)
    assert report.status is OracleStatus.OK, report.message
    assert compare(fixture_cases.run(case), report).outcome.value == "agree"
