"""The census of a corpus and the C1 slice chosen from it (ADR-0003)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.census._program import (
    CorpusProgram,
    Counts,
    ProgramCensus,
    Unparsable,
    census_program,
)

_FORM_NAME_END: Final = "("


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CorpusInfo(_Frozen):
    """Where a corpus came from: `source`, `config`, pinned `revision` and `licence`.

    Every census row set carries it, so a count is never separated from its licence.
    """

    source: str
    config: str
    revision: str
    licence: str


class FamilyCensus(_Frozen):
    """What one family of a corpus writes, counted over its programs (ADR-0003).

    `programs` = `parsed` + `unparsable`. `calls`, `forms`, `selectors`,
    `unknown` and `foreign` add the programs' counts; `end_forms` counts the
    parsed programs' end forms. The ranking triple is `distinct_calls`,
    `distinct_selectors`, `distinct_forms`: distinct keys, with calls on
    `builtin` and on other modules left out of the first and last.
    """

    family: str
    programs: int
    parsed: int
    unparsable: int
    calls: Counts
    forms: Counts
    selectors: Counts
    unknown: Counts
    foreign: Counts
    end_forms: Counts
    distinct_calls: int
    distinct_selectors: int
    distinct_forms: int

    @model_validator(mode="after")
    def _programs_add_up(self) -> FamilyCensus:
        if self.programs != self.parsed + self.unparsable:
            raise ValueError("programs is not parsed + unparsable")
        return self


class CensusReport(_Frozen):
    """The census of a corpus: totals, families in rank order, every unparsable program.

    Guarantees `programs` = `parsed` + `unparsable` = the corpus's size, each
    program in exactly one of the two, `families` in rank order (ascending by
    the ranking triple, then name) and `unparsable_programs` sorted by stem.
    `digest` is the SHA-256 of the report's canonical JSON without the digest
    field (sorted keys, no whitespace, ASCII); a report whose digest is not
    that of its content is refused, so a digest equal is a report equal.
    """

    corpus: CorpusInfo
    programs: int
    parsed: int
    unparsable: int
    families: tuple[FamilyCensus, ...]
    unparsable_programs: tuple[Unparsable, ...]
    digest: str

    @model_validator(mode="after")
    def _totals_add_up(self) -> CensusReport:
        if self.programs != self.parsed + self.unparsable:
            raise ValueError("programs is not parsed + unparsable")
        if self.unparsable != len(self.unparsable_programs):
            raise ValueError("unparsable does not match the unparsable list")
        if self.digest != _digest(self.model_dump(mode="json")):
            raise ValueError("digest is not that of the report's content")
        return self

    def to_json(self) -> str:
        """The report as canonical JSON, digest included: `from_json` returns an equal report.

        >>> info = CorpusInfo(source="s", config="c", revision="r", licence="l")
        >>> report = census([], info)
        >>> CensusReport.from_json(report.to_json()) == report
        True
        """
        return _canonical(self.model_dump(mode="json"))

    @classmethod
    def from_json(cls, text: str) -> Self:
        """Read a report written by `to_json`; refuses one whose digest does not match."""
        return cls.model_validate_json(text)


def _canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(data: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of a report's dump, its digest field left out."""
    body = {key: value for key, value in data.items() if key != "digest"}
    return hashlib.sha256(_canonical(body).encode("ascii")).hexdigest()


def _sorted(counter: Counter[str]) -> Counts:
    return tuple(sorted(counter.items()))


def _rank(family: FamilyCensus) -> tuple[int, int, int, str]:
    return (family.distinct_calls, family.distinct_selectors, family.distinct_forms, family.family)


class _Tally:
    def __init__(self, family: str) -> None:
        self.family = family
        self.parsed = 0
        self.unparsable = 0
        self.counters: dict[str, Counter[str]] = {
            name: Counter()
            for name in ("calls", "forms", "selectors", "unknown", "foreign", "end_forms")
        }
        self.ranked_calls: set[str] = set()
        self.ranked_forms: set[str] = set()

    def add(self, result: ProgramCensus | Unparsable) -> None:
        if isinstance(result, Unparsable):
            self.unparsable += 1
            return
        self.parsed += 1
        for name in ("calls", "forms", "selectors", "unknown", "foreign"):
            self.counters[name].update(dict(getattr(result, name)))
        self.counters["end_forms"][result.end_form] += 1
        foreign = {key for key, _ in result.foreign}
        self.ranked_calls.update(key for key, _ in result.calls if key not in foreign)
        self.ranked_forms.update(
            key for key, _ in result.forms if key.split(_FORM_NAME_END, 1)[0] not in foreign
        )

    def done(self) -> FamilyCensus:
        counters = self.counters
        return FamilyCensus(
            family=self.family,
            programs=self.parsed + self.unparsable,
            parsed=self.parsed,
            unparsable=self.unparsable,
            calls=_sorted(counters["calls"]),
            forms=_sorted(counters["forms"]),
            selectors=_sorted(counters["selectors"]),
            unknown=_sorted(counters["unknown"]),
            foreign=_sorted(counters["foreign"]),
            end_forms=_sorted(counters["end_forms"]),
            distinct_calls=len(self.ranked_calls),
            distinct_selectors=len(counters["selectors"]),
            distinct_forms=len(self.ranked_forms),
        )


def census(programs: Iterable[CorpusProgram], corpus: CorpusInfo) -> CensusReport:
    """Count every program of a corpus, never running one, and rank its families.

    Every program is in exactly one of `parsed` or `unparsable_programs`; a
    stem used twice is the caller's mistake and raises `ValueError`. Families
    rank ascending by (distinct calls, distinct selector strings, distinct API
    forms), then by name (ADR-0003).

    >>> info = CorpusInfo(source="s", config="c", revision="r", licence="l")
    >>> text = "import cadquery as cq\\nr = cq.Workplane('XY').box(1, 1, 1)\\n"
    >>> programs = [CorpusProgram(stem="a", family="f", text=text),
    ...             CorpusProgram(stem="b", family="f", text="(")]
    >>> report = census(programs, info)
    >>> report.programs, report.parsed, report.unparsable
    (2, 1, 1)
    >>> report.families[0].distinct_calls
    2
    """
    ordered = sorted(programs, key=lambda program: program.stem)
    stems = [program.stem for program in ordered]
    if len(set(stems)) != len(stems):
        raise ValueError("a stem is used by more than one program")
    tallies: dict[str, _Tally] = {}
    unparsable: list[Unparsable] = []
    for program in ordered:
        result = census_program(program)
        tallies.setdefault(program.family, _Tally(program.family)).add(result)
        if isinstance(result, Unparsable):
            unparsable.append(result)
    families = tuple(sorted((t.done() for t in tallies.values()), key=_rank))
    fields: dict[str, Any] = {
        "corpus": corpus,
        "programs": len(ordered),
        "parsed": len(ordered) - len(unparsable),
        "unparsable": len(unparsable),
        "families": families,
        "unparsable_programs": tuple(unparsable),
    }
    draft = CensusReport.model_construct(digest="", **fields)
    return CensusReport(digest=_digest(draft.model_dump(mode="json")), **fields)


def select_slice(
    report: CensusReport,
    programs: Iterable[CorpusProgram],
    families: int = 3,
    per_family: int = 100,
    min_programs: int = 100,
) -> tuple[str, ...]:
    """The stems of the slice: the first `per_family` by stem of each of the first
    `families` ranked families with at least `min_programs` programs.

    Families come in rank order, stems sorted as strings within each. Unparsable
    programs are in the slice like any other (it is a choice by stem). Raises
    `ValueError` when fewer than `families` families are eligible or one has
    fewer than `per_family` programs, and when `programs` disagrees with `report`.

    >>> info = CorpusInfo(source="s", config="c", revision="r", licence="l")
    >>> corpus = [CorpusProgram(stem=f"p{i}", family="f", text="x = 1") for i in range(4)]
    >>> select_slice(census(corpus, info), corpus, families=1, per_family=2, min_programs=3)
    ('p0', 'p1')
    """
    by_family: dict[str, list[str]] = {}
    for program in programs:
        by_family.setdefault(program.family, []).append(program.stem)
    chosen = [f for f in report.families if f.programs >= min_programs][:families]
    if len(chosen) < families:
        raise ValueError(f"{len(chosen)} families have {min_programs} programs, {families} wanted")
    stems: list[str] = []
    for family in chosen:
        family_stems = sorted(by_family.get(family.family, []))
        if len(family_stems) != family.programs:
            raise ValueError(f"programs disagree with the report for family {family.family!r}")
        stems.extend(family_stems[:per_family])
    return tuple(stems)
