"""The fidelity target's two figures over one corpus: reach and in-subset rows (ADR-0012).

`reach_report` joins a corpus's fidelity table with the static reach of its
programs. Every figure is over all programs; an unparsable program is a row
that is not in-subset, never a program left out. The target reads two fields,
`in_subset_cq_bug` and `in_subset_by_design`; agreement over all programs is
published beside them, never targeted.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.census import CorpusProgram, ProgramCensus, Unparsable, reach
from arris_gym.cq import Subset
from arris_gym.fidelity._compare import DisagreementClass, FidelityOutcome
from arris_gym.fidelity._table import Counts, FidelityTable

_OUTCOMES = [o.value for o in FidelityOutcome]
_CLASSES = [c.value for c in DisagreementClass]


def _counts(names: Iterable[str], members: list[str]) -> Counts:
    seen = Counter(names)
    return {member: seen[member] for member in members}


class ReachReport(BaseModel):
    """Reach, agreement and the in-subset rows of one corpus, over all its programs.

    Guarantees, validated: `in_subset` is at most `programs`, `agree` at most
    `programs`, `timed_out` at most `programs`; `in_subset_outcomes` and
    `in_subset_classes` hold every member of their enumeration and add up to
    `in_subset` (the classes to the in-subset disagreements); and
    `in_subset_cq_bug` and `in_subset_by_design` are the classes' own counts,
    named so that the target is two comparisons. `agree` counts the rows that
    agree, in or out of the subset; `timed_out` the rows where either side
    timed out. No fraction with a zero denominator is invented.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    programs: int
    in_subset: int
    agree: int
    timed_out: int
    in_subset_outcomes: Counts
    in_subset_classes: Counts
    in_subset_cq_bug: int
    in_subset_by_design: int

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name in ("in_subset", "agree", "timed_out"):
            if not 0 <= getattr(self, name) <= self.programs:
                raise ValueError(f"{name} must satisfy 0 <= {name} <= programs")
        if sorted(self.in_subset_outcomes) != sorted(_OUTCOMES) or sorted(
            self.in_subset_classes
        ) != sorted(_CLASSES):
            raise ValueError("a count lacks a member of its enumeration")
        if sum(self.in_subset_outcomes.values()) != self.in_subset:
            raise ValueError("in_subset_outcomes do not add up to in_subset")
        if sum(self.in_subset_classes.values()) != self.in_subset_outcomes["disagree"]:
            raise ValueError("in_subset_classes do not add up to the in-subset disagreements")
        if self.in_subset_cq_bug != self.in_subset_classes["cq_bug"]:
            raise ValueError("in_subset_cq_bug is not the cq_bug count")
        if self.in_subset_by_design != self.in_subset_classes["by_design"]:
            raise ValueError("in_subset_by_design is not the by_design count")
        return self

    def to_json(self) -> str:
        """The report as canonical JSON (sorted keys, no whitespace, ASCII)."""
        data: dict[str, Any] = self.model_dump(mode="json")
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def reach_report(
    table: FidelityTable,
    programs: Iterable[CorpusProgram | ProgramCensus | Unparsable],
    subset: Subset,
) -> ReachReport:
    """The reach report of `table`'s corpus under `subset`.

    `programs` are the corpus's source records or their census rows; their
    stems must be exactly the table's entry names, so that every program has a
    row and no row is orphaned. Raises `ValueError` otherwise, naming a few
    stems. Programs are parsed, never run.

    >>> from arris_gym.cq import subset
    >>> from arris_gym.fidelity import fidelity_table
    >>> reach_report(fidelity_table([]), [], subset()).programs
    0
    """
    outcomes = list(programs)
    found = reach(outcomes, subset)
    names = {entry.name for entry in table.entries}
    stems = {p.stem for p in outcomes}
    if names != stems:
        raise ValueError(
            f"programs without a row: {sorted(stems - names)[:5]}; "
            f"rows without a program: {sorted(names - stems)[:5]}"
        )
    inside = set(found.stems)
    rows = [entry.row for entry in table.entries if entry.name in inside]
    classes = _counts((r.disagreement.value for r in rows if r.disagreement is not None), _CLASSES)
    return ReachReport(
        programs=table.programs,
        in_subset=found.in_subset,
        agree=table.outcomes["agree"],
        timed_out=len(table.timed_out),
        in_subset_outcomes=_counts((r.outcome.value for r in rows), _OUTCOMES),
        in_subset_classes=classes,
        in_subset_cq_bug=classes["cq_bug"],
        in_subset_by_design=classes["by_design"],
    )
