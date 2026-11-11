"""Deterministic, greedy reach curves, without executing corpus programs."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.census._program import CorpusProgram, ProgramCensus, Unparsable, census_program
from arris_gym.census._reach import Reach, _eligible, _missing_forms, reach
from arris_gym.census._report import _canonical, _digest
from arris_gym.cq import Subset


class ReachStep(BaseModel):
    """One additional census API form and the in-subset count after admitting it."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    form: str
    in_subset: int


class ReachCurve(BaseModel):
    """Initial reach and greedy API-form admissions, with every program counted.

    Selectors, end forms, unknown receivers and foreign calls stay fixed.
    Counts never decrease or exceed the all-program denominator. Forms are
    unique. The digest names canonical JSON excluding its own field.
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
        forms = [step.form for step in self.steps]
        if len(set(forms)) != len(forms):
            raise ValueError("a form is admitted more than once")
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


def reach_curve(
    programs: Iterable[CorpusProgram | ProgramCensus | Unparsable], subset: Subset
) -> ReachCurve:
    """Admit missing census forms greedily by programs unlocked, ties by form key.

    Each step hypothetically admits one exact census form, without changing
    the runtime subset. A form used often can rank after a rarer form when
    the latter alone unlocks more programs. Zero-gain steps are retained:
    programs needing several forms may unlock only after these bridges.
    Selectors, end forms, unknown receivers and foreign calls never change.
    Unparsable programs remain in the denominator. Input order cannot move
    the curve or digest; duplicate stems raise ValueError.

    >>> from arris_gym.cq import subset
    >>> text = "import cadquery as cq\\nresult = cq.Workplane()"
    >>> p = CorpusProgram(stem="a", family="f", text=text)
    >>> curve = reach_curve([p], subset())
    >>> curve.initial.in_subset, curve.steps[0].form, curve.steps[0].in_subset
    (0, 'cq.Workplane()', 1)
    """
    rows = [census_program(p) if isinstance(p, CorpusProgram) else p for p in programs]
    initial = reach(rows, subset)
    missing = [
        _missing_forms(p, subset)
        for p in rows
        if isinstance(p, ProgramCensus) and _eligible(p, subset)
    ]
    # Missing forms of blocked programs are retained too: their zero gain
    # states explicitly that lifting API forms cannot remove other blockers.
    remaining: set[str] = set().union(
        *(_missing_forms(p, subset) for p in rows if isinstance(p, ProgramCensus))
    )
    pending = Counter(forms for forms in missing if forms)
    count = initial.in_subset
    steps: list[ReachStep] = []
    while remaining:
        gains = Counter({min(forms): n for forms, n in pending.items() if len(forms) == 1})
        form = min(remaining, key=lambda key: (-gains[key], key))
        count += gains[form]
        steps.append(ReachStep(form=form, in_subset=count))
        remaining.remove(form)
        updated: Counter[frozenset[str]] = Counter()
        for forms, n in pending.items():
            reduced = forms - {form}
            if reduced:
                updated[reduced] += n
        pending = updated
    draft = ReachCurve.model_construct(initial=initial, steps=tuple(steps), digest="")
    return ReachCurve(
        initial=initial, steps=tuple(steps), digest=_digest(draft.model_dump(mode="json"))
    )
