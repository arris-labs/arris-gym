"""The calibration set under `cq` (plans/m3-cq-subset step 9, ADR-0005, ADR-0007).

Each `tests/fixtures/fidelity/agree-*/oracle.py` is a calibration part as
CadQuery writes it. Under `dialect="cq"` a program that uses only the subset
must match its `expected.json` closed form; any other must end
`unsupported_api`, naming its first call outside the subset in evaluation
order. The subset takes the census's forms (ADR-0007), and `cq.Workplane()`
with no plane is not one of them: the census writes `cq.Workplane(str)` only,
and step 6 refuses the bare form on purpose. So every program here that names
no plane ends at its first line, and `agree-cylinder` and `agree-hexagon-prism`,
which would otherwise match, are open for the conductor (plans/m3-cq-subset).
The `XZ` revolves run since `cq.Workplane('XZ')` was lifted
(plans/in-subset-cq-bugs step 4): the frustum and the washer match their
closed forms, the sphere and the torus name their next call outside.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import arris_gym
from arris_gym import Status
from arris_gym.fidelity import BOUNDS_ABS

ROOT = pathlib.Path(__file__).resolve().parent / "fixtures" / "fidelity"
DIRECTORIES = sorted(ROOT.glob("agree-*"))
# The first call outside the subset of each program, read from its text in
# evaluation order, as `UnsupportedApi` names it. `None` marks a program that
# uses only the subset: it must then match its closed form.
FIRST_OUTSIDE: dict[str, str | None] = {
    "agree-box": "cq.Workplane()",
    "agree-box-blind-hole": "cq.Workplane()",
    "agree-box-minus-notch": "cq.Workplane()",
    "agree-box-offset": "cq.Workplane()",
    "agree-box-through-hole": "cq.Workplane()",
    "agree-box-two-holes": "cq.Workplane()",
    "agree-chamfer-one-edge": "cq.Workplane()",
    "agree-chamfer-top-ring": "cq.Workplane()",
    "agree-cylinder": "cq.Workplane()",
    "agree-cylinder-offset": "cq.Workplane()",
    "agree-fillet-one-edge": "cq.Workplane()",
    "agree-fillet-vertical-edges": "cq.Workplane()",
    "agree-hexagon-prism": "cq.Workplane()",
    "agree-l-prism-fuse": "cq.Workplane()",
    "agree-revolve-frustum": None,
    "agree-revolve-sphere": "Workplane.threePointArc",
    "agree-revolve-torus": "Workplane.center",
    "agree-revolve-washer": None,
    "agree-tube": "cq.Workplane()",
}


def flat(corners: object) -> list[float]:
    # `expected.json` gives lists; `Measures.bounds` gives tuples.
    assert isinstance(corners, list | tuple)
    return [float(x) for corner in corners for x in corner]


def test_every_calibration_program_is_named_here() -> None:
    assert sorted(FIRST_OUTSIDE) == [d.name for d in DIRECTORIES]


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_a_calibration_program_under_cq_matches_or_names_its_first_outside_call(
    d: pathlib.Path,
) -> None:
    first = FIRST_OUTSIDE[d.name]
    result = arris_gym.run((d / "oracle.py").read_text(), dialect="cq")
    if first is not None:
        assert result.status is Status.UNSUPPORTED_API, result.message
        assert result.message == first
        return
    want = json.loads((d / "expected.json").read_text())
    assert result.status is Status.OK, result.message
    assert result.measures is not None
    assert result.measures.volume == pytest.approx(want["volume"], rel=1e-12)
    assert result.measures.area == pytest.approx(want["area"], rel=1e-12)
    assert result.measures.centroid == pytest.approx(want["centroid"], abs=1e-9)
    assert flat(result.measures.bounds) == pytest.approx(flat(want["bounds"]), abs=BOUNDS_ABS)
