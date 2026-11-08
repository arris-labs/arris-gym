"""The committed slice is the one the committed census chooses (ADR-0003, delta 2)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from arris_gym.census import CensusReport

C1 = Path(__file__).parent / "fixtures" / "c1"
FAMILIES = 3
PER_FAMILY = 100
MIN_PROGRAMS = 100


def test_slice_matches_census() -> None:
    report = CensusReport.from_json((C1 / "census.json").read_text(encoding="utf-8"))
    lines = (C1 / "slice.txt").read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    stems = [line for line in lines if not line.startswith("#")]
    assert len(stems) == len(set(stems)) == FAMILIES * PER_FAMILY
    assert f"# census digest: {report.digest}" in header

    eligible = [f.family for f in report.families if f.programs >= MIN_PROGRAMS][:FAMILIES]
    assert f"# families: {', '.join(eligible)}" in header
    # Stems are `<family>_<number>_<suffix>`; families are found by prefix, longest first.
    owners: Counter[str] = Counter()
    for index, family in enumerate(eligible):
        block = stems[index * PER_FAMILY : (index + 1) * PER_FAMILY]
        assert block == sorted(block)
        assert all(stem.startswith(family + "_") for stem in block)
        owners[family] = len(block)
    assert owners == Counter({family: PER_FAMILY for family in eligible})
