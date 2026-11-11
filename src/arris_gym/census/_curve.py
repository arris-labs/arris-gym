"""Deterministic, greedy reach curves, without executing corpus programs."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.census._program import CorpusProgram, ProgramCensus, Unparsable, census_program
from arris_gym.census._reach import (
    Reach,
    _end_admitted,
    _foreign_admitted,
    _missing_forms,
    reach,
)
from arris_gym.census._report import _canonical, _digest
from arris_gym.cq import Subset

Kind = Literal["end_form", "form", "selector"]
"""What a curve step admits: a census end form, API form or selector."""


class ReachStep(BaseModel):
    """One additional census item of `kind` and the in-subset count after admitting it."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Kind
    item: str
    in_subset: int


class ReachCurve(BaseModel):
    """Initial reach and greedy admissions of forms, selectors and end forms.

    Unknown receivers and foreign calls outside the admitted list stay fixed.
    Counts never decrease or exceed the all-program denominator. Each
    `(kind, item)` is admitted once. The digest names canonical JSON excluding its own field.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    initial: Reach
    steps: tuple[ReachStep, ...]
    digest: str

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        counts = [self.initial.in_subset, *(step.in_subset for step in self.steps)]
        if counts != sorted(counts) or counts[-1] > self.initial.programs:
            raise ValueError("reach counts must increase within the all-program denominator")
        items = [(step.kind, step.item) for step in self.steps]
        if len(set(items)) != len(items):
            raise ValueError("an item is admitted more than once")
        if self.digest != _digest(self.model_dump(mode="json")):
            raise ValueError("digest is not that of the curve's content")
        return self

    def to_json(self) -> str:
        """Canonical JSON including the validated digest; `from_json` reads it."""
        return _canonical(self.model_dump(mode="json"))

    @classmethod
    def from_json(cls, text: str) -> Self:
        """Read canonical JSON, preserving lone surrogates and checking the digest."""
        return cls.model_validate(json.loads(text))


Item = tuple[Kind, str]


def _missing(program: ProgramCensus, subset: Subset) -> frozenset[Item]:
    items: set[Item] = {("form", form) for form in _missing_forms(program, subset)}
    items.update(("selector", sel) for sel, _ in program.selectors if sel not in subset.selectors)
    if not _end_admitted(program.end_form, subset):
        items.add(("end_form", program.end_form))
    return frozenset(items)


def _unlockable(program: ProgramCensus) -> bool:
    return not program.unknown and all(_foreign_admitted(call) for call, _ in program.foreign)


def reach_curve(
    programs: Iterable[CorpusProgram | ProgramCensus | Unparsable], subset: Subset
) -> ReachCurve:
    """Admit missing census items greedily: programs unlocked, then programs using it.

    An item is an exact census API form, selector or end form; each step
    hypothetically admits one, without changing the runtime subset. The next
    item unlocks the most programs immediately. When several tie, zero among
    them, the one missing from the most programs that admitting items can
    still unlock goes first, then by kind and key. So a corpus whose programs
    all need several items is bridged in the order its programs share them,
    not alphabetically. Items only blocked programs use (an unknown receiver,
    a foreign call outside the admitted list) come last with zero gain: those
    blockers never move. Unparsable programs stay in the denominator. Input
    order cannot move the curve or digest; duplicate stems raise ValueError.

    >>> from arris_gym.cq import subset
    >>> text = "import cadquery as cq\\nr = cq.Workplane()"
    >>> p = CorpusProgram(stem="a", family="f", text=text)
    >>> [(s.kind, s.item, s.in_subset) for s in reach_curve([p], subset()).steps]
    [('end_form', 'r = …', 0), ('form', 'cq.Workplane()', 1)]
    """
    rows = [census_program(p) if isinstance(p, CorpusProgram) else p for p in programs]
    initial = reach(rows, subset)
    parsed = [p for p in rows if isinstance(p, ProgramCensus)]
    remaining: set[Item] = set().union(*(_missing(p, subset) for p in parsed))
    pending = Counter(m for p in parsed if _unlockable(p) and (m := _missing(p, subset)))
    count = initial.in_subset
    steps: list[ReachStep] = []
    while remaining:
        gains: Counter[Item] = Counter()
        usage: Counter[Item] = Counter()
        for items, n in pending.items():
            if len(items) == 1:
                gains[min(items)] += n
            for missing in items:
                usage[missing] += n
        kind, item = min(remaining, key=lambda key: (-gains[key], -usage[key], key))
        count += gains[(kind, item)]
        steps.append(ReachStep(kind=kind, item=item, in_subset=count))
        remaining.remove((kind, item))
        updated: Counter[frozenset[Item]] = Counter()
        for items, n in pending.items():
            if reduced := items - {(kind, item)}:
                updated[reduced] += n
        pending = updated
    draft = ReachCurve.model_construct(initial=initial, steps=tuple(steps), digest="")
    return ReachCurve(
        initial=initial, steps=tuple(steps), digest=_digest(draft.model_dump(mode="json"))
    )
