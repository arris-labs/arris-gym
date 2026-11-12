"""Fixture loader: `tests/fixtures/<area>/<slug>/{program.py,expected.json}`.

docs/ROADMAP.md §Fixtures gives the layout. An expected value comes from a
closed form or from how the part was built, never from arris-gym's output.
"""

from __future__ import annotations

import json
import pathlib
import platform
from dataclasses import dataclass, replace

import arris_gym
from arris_gym import ExecResult, Status, cq

ROOT = pathlib.Path(__file__).resolve().parent / "fixtures"
# Relative to the larger of 1 and the expected magnitude. The kernel pads a
# body's bounds by its own tolerance (2e-7) and rounds a sum in its last bits,
# so this is wide of both and far below any real modelling error. A fixture
# that needs another names it in expected.json with the ADR that decided it
# (tools/check-fixtures.sh); a case that fails at this one is an xfail
# regression fixture instead.
DEFAULT_TOLERANCE = 1e-6
# The deadline, in seconds, a fixture expected to end in `timeout` runs to;
# its expected message names it. Every other fixture runs to `run`'s default.
TIMEOUT_DEADLINE = 1.0
# The key a fixture declares in place of `message` when the same program's
# message differs by machine: `platform.machine()` -> message. Its fixture
# directory holds a README.md saying why (tools/check-fixtures.sh).
BY_MACHINE = "message_by_machine"


def c1_subset() -> cq.Subset:
    """The subset the committed `c2/` census curves and baseline were measured under.

    Today's subset less what C2 has lifted since: ADR-0015's `r = …`
    (plans/in-subset-cq-bugs step 2), `cq.Workplane`'s `origin=` (step 6)
    and `Workplane.workplane` (step 7).
    """
    constructor = cq.CensusForm("cq.Workplane", (("str",),))
    return replace(
        cq.subset(),
        forms=tuple(
            constructor if form.name == "cq.Workplane" else form
            for form in cq.subset().forms
            if form.name != "Workplane.workplane"
        ),
        end_forms=("result = …", "show_object(…)"),
    )


@dataclass(frozen=True)
class Case:
    """One fixture: its directory name, program text and expected JSON."""

    slug: str
    program: str
    expected: dict[str, object]


def load(area: str) -> list[Case]:
    """Every fixture under `tests/fixtures/<area>/`, sorted by slug.

    Raises `ValueError` for a fixture outside `regression/` whose measures
    leave out `faces` or `face_kinds`: only a desired, unbuilt body may; and
    for one whose message is declared per machine but not for this one
    (`for_machine`).
    """
    cases = []
    for directory in sorted((ROOT / area).iterdir()):
        if (directory / "program.py").is_file():
            declared = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
            expected = for_machine(declared, f"{area}/{directory.name}", platform.machine())
            measures = expected.get("measures")
            counted = isinstance(measures, dict) and {"faces", "face_kinds"} <= measures.keys()
            if area != "regression" and isinstance(measures, dict) and not counted:
                raise ValueError(f"{area}/{directory.name}: measures without face counts")
            cases.append(
                Case(
                    directory.name, (directory / "program.py").read_text(encoding="utf-8"), expected
                )
            )
    return cases


def for_machine(expected: dict[str, object], where: str, machine: str) -> dict[str, object]:
    """`expected` with its message for `machine`, a `platform.machine()` name.

    A fixture without `message_by_machine` comes back unchanged: one
    expectation on every machine. One with it gets that machine's entry as its
    `message`. Raises `ValueError` when it declares nothing for `machine`, or
    declares `message` beside it: a machine nobody wrote an expectation for
    never passes silently.
    """
    if BY_MACHINE not in expected:
        return expected
    by_machine = expected[BY_MACHINE]
    if "message" in expected or not isinstance(by_machine, dict):
        raise ValueError(f"{where}: {BY_MACHINE} is a mapping, declared in place of message")
    if machine not in by_machine:
        declared = ", ".join(sorted(by_machine))
        raise ValueError(f"{where}: no expected message for machine {machine!r} ({declared})")
    resolved = {k: v for k, v in expected.items() if k != BY_MACHINE}
    resolved["message"] = by_machine[machine]
    return resolved


def run(case: Case) -> ExecResult:
    """Run a fixture's program alone in its expected dialect, a `timeout`
    fixture to `TIMEOUT_DEADLINE`."""
    dialect = str(case.expected["dialect"])
    if case.expected["status"] == Status.TIMEOUT.value:
        return arris_gym.run(case.program, dialect=dialect, timeout=TIMEOUT_DEADLINE)
    return arris_gym.run(case.program, dialect=dialect)


def close(actual: float, expected: float, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """Whether `actual` is within `tolerance` of `expected` (see DEFAULT_TOLERANCE)."""
    return abs(actual - expected) <= tolerance * max(1.0, abs(expected))


def check(result: ExecResult, expected: dict[str, object]) -> list[str]:
    """What differs between a result and a fixture's expectation; empty if nothing."""
    problems: list[str] = []
    tolerance = float(str(expected.get("tolerance", DEFAULT_TOLERANCE)))
    if result.status.value != expected["status"]:
        problems.append(f"status {result.status.value}, expected {expected['status']}")
    if result.dialect.value != expected["dialect"]:
        problems.append(f"dialect {result.dialect.value}, expected {expected['dialect']}")
    if "message" in expected and result.message != expected["message"]:
        problems.append(f"message {result.message!r}, expected {expected['message']!r}")
    refusal = expected.get("refusal")
    if isinstance(refusal, dict):
        if result.refusal is None:
            problems.append("no refusal")
        else:
            got = result.refusal.model_dump()
            got["entities"] = list(result.refusal.entities)
            if got != refusal:
                problems.append(f"refusal {got}, expected {refusal}")
    elif result.refusal is not None:
        problems.append(f"unexpected refusal {result.refusal}")
    violations = expected.get("violations")
    if isinstance(violations, list) and list(result.violations) != violations:
        problems.append(f"violations {list(result.violations)}, expected {violations}")
    measures = expected.get("measures")
    if isinstance(measures, dict):
        if result.measures is None:
            problems.append("no measures")
        else:
            problems += _measures_differ(result, measures, tolerance)
    elif result.measures is not None:
        problems.append("unexpected measures")
    return problems


def _flatten(value: object) -> list[float]:
    if isinstance(value, (list, tuple)):
        return [x for item in value for x in _flatten(item)]
    return [float(str(value))]


def _measures_differ(
    result: ExecResult, expected: dict[str, object], tolerance: float
) -> list[str]:
    assert result.measures is not None
    problems = []
    for name in ("volume", "area", "centroid", "bounds"):
        got = _flatten(getattr(result.measures, name))
        want = _flatten(expected[name])
        if len(got) != len(want) or not all(
            close(g, w, tolerance) for g, w in zip(got, want, strict=True)
        ):
            problems.append(f"{name} {got}, expected {want}")
    for name in ("shells", "genus"):
        if getattr(result.measures, name) != expected[name]:
            problems.append(f"{name} {getattr(result.measures, name)}, expected {expected[name]}")
    # Only a regression fixture may leave the face counts out: its desired body
    # is not built yet, and how the kernel splits faces is carried, never
    # judged (ADR-0005), so no construction gives them.
    if "faces" in expected and result.measures.faces != expected["faces"]:
        problems.append(f"faces {result.measures.faces}, expected {expected['faces']}")
    kinds = [list(pair) for pair in result.measures.face_kinds]
    if "face_kinds" in expected and kinds != expected["face_kinds"]:
        problems.append(f"face_kinds {kinds}, expected {expected['face_kinds']}")
    return problems
