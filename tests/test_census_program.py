"""`census_program` counts what a program writes and never raises (ADR-0003).

The fixtures under `tests/fixtures/census/` were counted by hand from each
program; the properties build programs whose counts are known by construction.
"""

from __future__ import annotations

import doctest
import keyword
import warnings
from collections import Counter
from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import fixture_cases
from arris_gym.census import (
    NON_LITERAL,
    SELECTOR_METHODS,
    CorpusProgram,
    ProgramCensus,
    Unparsable,
    _program,
    census_program,
)

CASES = fixture_cases.load("census")


def census(text: str, stem: str = "p") -> ProgramCensus | Unparsable:
    """The census of `text`, with every warning raised as an error around it."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return census_program(CorpusProgram(stem=stem, family="fixture", text=text))


def counts(c: ProgramCensus) -> dict[str, object]:
    """A census as its fixture's `expected.json` writes it."""
    return {
        "calls": dict(c.calls),
        "forms": dict(c.forms),
        "selectors": dict(c.selectors),
        "unknown": dict(c.unknown),
        "end_form": c.end_form,
    }


@pytest.mark.parametrize("case", CASES, ids=[c.slug for c in CASES])
def test_a_census_fixture_counts_what_its_program_writes(case: fixture_cases.Case) -> None:
    got = census(case.program, stem=case.slug)
    assert got.stem == case.slug
    if "kind" in case.expected:
        assert isinstance(got, Unparsable), counts(got) if isinstance(got, ProgramCensus) else got
        assert (got.kind, got.message) == (case.expected["kind"], case.expected["message"])
    else:
        assert isinstance(got, ProgramCensus), got
        assert counts(got) == case.expected


def test_the_fixtures_cover_every_unparsable_kind_the_plan_names() -> None:
    kinds = {str(c.expected["kind"]) for c in CASES if "kind" in c.expected}
    assert kinds == {"SyntaxError", "RecursionError", "MemoryError"}


def test_a_count_out_of_key_order_is_refused() -> None:
    with pytest.raises(ValidationError, match="sorted"):
        ProgramCensus(
            stem="p",
            calls=(("b", 1), ("a", 1)),
            forms=(),
            selectors=(),
            unknown=(),
            end_form="other",
        )
    with pytest.raises(ValidationError, match="below 1"):
        ProgramCensus(stem="p", calls=(("a", 0),), forms=(), selectors=(), unknown=(), end_form="")


def test_the_doctests_of_the_census_run() -> None:
    assert doctest.testmod(_program).failed == 0


# Fragments that put drawn text near Python, so many draws parse and many do not.
FRAGMENTS = (
    "import cadquery as cq\n",
    "from cadquery import Workplane as W\n",
    "cq.Workplane(",
    "W(",
    ".faces(",
    ".union(",
    "'>Z'",
    '"\\d"',
    ")",
    "(",
    "[",
    "]",
    ",",
    "*",
    "**",
    "=",
    " = ",
    "x",
    "result",
    "1",
    "-",
    ".",
    ":",
    "lambda: ",
    "def f(a):\n    ",
    "return ",
    "for p in x:\n    ",
    "match x:\n    case [*r]:\n        ",
    "show_object(",
    "\n",
    "\x00",
    "\ud800",
    "\\",
    "#",
)


@given(st.text() | st.lists(st.sampled_from(FRAGMENTS), max_size=40).map("".join))
def test_census_program_never_raises_on_any_text(text: str) -> None:
    got = census(text)
    assert isinstance(got, ProgramCensus | Unparsable)
    assert got.stem == "p"


IDENTIFIER = st.from_regex(r"[a-z][A-Za-z0-9_]{0,7}", fullmatch=True).filter(
    lambda name: not keyword.iskeyword(name)
)


@dataclass(frozen=True)
class Arg:
    """An argument's source text, its kind, the calls its text makes itself, and
    the string a `str` literal holds."""

    text: str
    kind: str
    calls: tuple[tuple[str, str], ...] = ()  # (call, form) pairs
    string: str | None = None

    @property
    def selector(self) -> str:
        return self.string if self.string is not None else NON_LITERAL


ARGS = st.one_of(
    st.text(max_size=8).map(lambda s: Arg(repr(s), "str", string=s)),
    st.integers(-(10**12), 10**12).map(lambda n: Arg(repr(n), "num")),
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: Arg(repr(f), "num")),
    st.booleans().map(lambda b: Arg(repr(b), "bool")),
    st.just(Arg("None", "none")),
    st.just(Arg("(1, 2)", "tuple")),
    st.just(Arg("[0, 1]", "list")),
    st.just(Arg("x", "name")),
    st.just(Arg("x + 1", "expr")),
    st.just(
        Arg(
            "cq.Vector(1, 2, 3)",
            "call",
            (("cq.Vector", "cq.Vector(num, num, num)"),),
        )
    ),
)


@dataclass(frozen=True)
class Link:
    """One drawn method call of a chain."""

    method: str
    args: tuple[Arg, ...]
    keywords: tuple[tuple[str, Arg], ...]  # sorted by name

    def text(self) -> str:
        parts = [a.text for a in self.args] + [f"{k}={a.text}" for k, a in self.keywords]
        return f".{self.method}({', '.join(parts)})"

    def form(self) -> str:
        positional = ", ".join(a.kind for a in self.args)
        named = ", ".join(f"{k}={a.kind}" for k, a in self.keywords)
        inside = f"{positional}; {named}" if positional and named else positional or named
        return f"Workplane.{self.method}({inside})"

    def selector(self) -> str | None:
        if self.method not in SELECTOR_METHODS:
            return None
        if self.args:
            return self.args[0].selector
        return next((a.selector for k, a in self.keywords if k == "selector"), None)


LINKS = st.builds(
    Link,
    st.one_of(IDENTIFIER, st.sampled_from(SELECTOR_METHODS)),
    st.lists(ARGS, max_size=3).map(tuple),
    st.dictionaries(st.one_of(IDENTIFIER, st.just("selector")), ARGS, max_size=3).map(
        lambda d: tuple(sorted(d.items()))
    ),
)


@given(st.lists(LINKS, max_size=8), st.booleans())
def test_a_chain_built_from_drawn_calls_counts_exactly_those_calls(
    links: list[Link], one_statement_per_call: bool
) -> None:
    lines = ["import cadquery as cq", "x = 1", "result = cq.Workplane('XY')"]
    if one_statement_per_call:
        lines += [f"result = result{link.text()}" for link in links]
    else:
        lines[-1] += "".join(link.text() for link in links)
    calls: Counter[str] = Counter({"cq.Workplane": 1})
    forms: Counter[str] = Counter({"cq.Workplane(str)": 1})
    selectors: Counter[str] = Counter()
    for link in links:
        calls[f"Workplane.{link.method}"] += 1
        forms[link.form()] += 1
        for arg in (*link.args, *(a for _, a in link.keywords)):
            for call, form in arg.calls:
                calls[call] += 1
                forms[form] += 1
        selector = link.selector()
        if selector is not None:
            selectors[selector] += 1

    got = census("\n".join(lines) + "\n")

    assert isinstance(got, ProgramCensus), got
    assert dict(got.calls) == calls
    assert dict(got.forms) == forms
    assert dict(got.selectors) == selectors
    assert got.unknown == ()
    assert got.end_form == "result = …"
