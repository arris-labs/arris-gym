"""Static reach over every program, including every unparsable one (ADR-0012)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.census._foreign import STDLIB_ROOTS
from arris_gym.census._program import (
    _PYTHON_BUILTINS,
    CorpusProgram,
    ProgramCensus,
    Unparsable,
    census_program,
)
from arris_gym.cq import Subset


class Reach(BaseModel):
    """The in-subset count and sorted stems over all `programs`, never survivors.

    Refuses negative counts, an in-subset count above the denominator,
    duplicate or unsorted stems, and a count that differs from their length.
    An empty corpus has counts zero; no fraction with a zero denominator is
    invented. The record and its stems are frozen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    programs: int
    in_subset: int
    stems: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not 0 <= self.in_subset <= self.programs:
            raise ValueError("counts must satisfy 0 <= in_subset <= programs")
        if self.in_subset != len(self.stems):
            raise ValueError("in_subset differs from the number of stems")
        if list(self.stems) != sorted(set(self.stems)):
            raise ValueError("stems must be sorted and unique")
        return self


def _foreign_admitted(call: str) -> bool:
    root, _, tail = call.partition(".")
    if root in ("builtin", "builtins"):
        return tail in _PYTHON_BUILTINS or (root == "builtin" and tail == "show_object")
    return root in STDLIB_ROOTS


def _end_admitted(end_form: str, subset: Subset) -> bool:
    if end_form in subset.end_forms:
        return True
    if "show_object(…)" not in subset.end_forms:
        return False
    return (
        end_form.startswith("show_object(")
        and end_form.endswith(")")
        and end_form[len("show_object(") : -1].isidentifier()
    )


def _eligible(program: ProgramCensus | Unparsable, subset: Subset) -> bool:
    if isinstance(program, Unparsable) or program.unknown:
        return False
    if not _end_admitted(program.end_form, subset):
        return False
    if any(selector not in subset.selectors for selector, _ in program.selectors):
        return False
    foreign = dict(program.foreign)
    return all(_foreign_admitted(call) for call in foreign)


def _missing_forms(program: ProgramCensus, subset: Subset) -> frozenset[str]:
    foreign = dict(program.foreign)
    return frozenset(
        form
        for form, _ in program.forms
        if form.partition("(")[0] not in foreign and not subset.admits(form)
    )


def _in_subset(program: ProgramCensus | Unparsable, subset: Subset) -> bool:
    return (
        isinstance(program, ProgramCensus)
        and _eligible(program, subset)
        and not _missing_forms(program, subset)
    )


def reach(programs: Iterable[CorpusProgram | ProgramCensus | Unparsable], subset: Subset) -> Reach:
    """Count programs admitted by `subset`, statically, over every supplied program.

    Text is parsed, never run; precomputed census outcomes are also accepted.
    ADR-0012 requires admitted forms, selectors and end form, no unknown
    receiver, and foreign calls rooted in the fixed Python standard library
    list or the interpreter's builtins. An unparsable program is outside.
    Input order cannot change the record. Duplicate stems raise ValueError.

    >>> from arris_gym.cq import subset
    >>> programs = [CorpusProgram(stem="a", family="f", text="result = 1"),
    ...             CorpusProgram(stem="b", family="f", text="(")]
    >>> reach(programs, subset())
    Reach(programs=2, in_subset=1, stems=('a',))
    """
    outcomes = [census_program(p) if isinstance(p, CorpusProgram) else p for p in programs]
    stems = [p.stem for p in outcomes]
    if len(set(stems)) != len(stems):
        raise ValueError("a stem is used by more than one program")
    admitted = tuple(sorted(p.stem for p in outcomes if _in_subset(p, subset)))
    return Reach(programs=len(outcomes), in_subset=len(admitted), stems=admitted)
