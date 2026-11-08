"""The committed slice is the one the committed census chooses (ADR-0003, delta 2)."""

from __future__ import annotations

import re
from pathlib import Path

from arris_gym.census import CensusReport

C1 = Path(__file__).parent / "fixtures" / "c1"
FAMILIES = 3
PER_FAMILY = 100
MIN_PROGRAMS = 100
STEM = re.compile(r"(.+)_\d+_[^_]+")


def family_of(stem: str) -> str:
    match = STEM.fullmatch(stem)
    assert match, stem
    return match.group(1)


def test_slice_matches_census() -> None:
    report = CensusReport.from_json((C1 / "census.json").read_text(encoding="utf-8"))
    lines = (C1 / "slice.txt").read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    stems = [line for line in lines if not line.startswith("#")]
    assert len(stems) == len(set(stems)) == FAMILIES * PER_FAMILY
    assert f"# census digest: {report.digest}" in header

    eligible = [f.family for f in report.families if f.programs >= MIN_PROGRAMS][:FAMILIES]
    assert f"# families: {', '.join(eligible)}" in header
    by_name = {f.family: f for f in report.families}
    for index, family in enumerate(eligible):
        block = stems[index * PER_FAMILY : (index + 1) * PER_FAMILY]
        assert block == sorted(block)
        # A stem is `<family>_<number>_<suffix>`; the family is all before the number.
        assert {family_of(stem) for stem in block} == {family}
        assert by_name[family].programs >= len(block) == PER_FAMILY
