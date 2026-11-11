"""ADR-0012's static rule, from programs constructed one clause at a time."""

from __future__ import annotations

import doctest
import gzip
import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import fixture_cases
from arris_gym import Status, cq, run
from arris_gym.census import (
    CorpusProgram,
    ProgramCensus,
    Reach,
    Unparsable,
    _reach,
    census_program,
    reach,
)
from arris_gym.cq import _subset

CASES = fixture_cases.load("reach")
SUBSET = cq.subset()


def program(text: str, stem: str = "p") -> CorpusProgram:
    return CorpusProgram(stem=stem, family="fixture", text=text)


@pytest.mark.parametrize("case", CASES, ids=[case.slug for case in CASES])
def test_a_reach_fixture_decides_the_static_rule(case: fixture_cases.Case) -> None:
    p = program(case.program, case.slug)
    expected = bool(case.expected["in_subset"])
    got = reach([p], SUBSET)
    assert got.programs == 1
    assert got.in_subset == int(expected)
    assert got.stems == ((case.slug,) if expected else ())
    assert reach([census_program(p)], SUBSET) == got


@pytest.mark.parametrize(
    ("form", "admitted"),
    [
        ("cq.Workplane(str)", True),
        ("cq.Workplane()", False),
        ("cq.Workplane(num)", False),
        ("Workplane.extrude(name)", True),
        ("Workplane.extrude(expr)", True),
        ("Workplane.extrude(call)", True),
        ("Workplane.extrude(bool)", False),
        ("Workplane.extrude(list)", False),
        ("Workplane.union(none)", True),
        ("Workplane.transformed(offset=call, rotate=name)", True),
        ("Workplane.transformed(offset=tuple)", False),
        ("Workplane.transformed(offset=bool)", False),
        ("Workplane.transformed(offset=call, offset=call)", False),
        ("Workplane.transformed(rotate=call, offset=call)", False),
        ("Workplane.transformed(offset=call; )", False),
        ("Workplane.transformed(offset=)", False),
        ("Workplane.extrude( num)", False),
        ("Workplane.extrude(num,)", False),
        ("Workplane.extrude(*list)", False),
        ("Workplane.extrude(**dict)", False),
        ("Workplane.extrude(num; both=bool)", False),
        ("Workplane.extrude(num)ignored", False),
        ("Workplane.extrude(num", False),
        ("Workplane.extrude", False),
        ("cq.subset()", False),
    ],
)
def test_admits_checks_literal_kinds_count_and_canonical_keywords(
    form: str, admitted: bool
) -> None:
    assert SUBSET.admits(form) is admitted


def test_selectors_are_required_even_after_a_call_form_is_admitted() -> None:
    p = program("import cadquery as cq\nresult = cq.Workplane('XY').faces('>Z')")
    with_faces = replace(
        SUBSET, forms=(*SUBSET.forms, cq.CensusForm("Workplane.faces", (("str",),)))
    )
    assert reach([p], with_faces).in_subset == 0
    assert reach([p], replace(with_faces, selectors=(">Z",))).in_subset == 1
    assert reach([p], replace(with_faces, selectors=("<Z",))).in_subset == 0


def test_unknown_receiver_cannot_be_admitted_by_a_declaration() -> None:
    p = program("result = unknown(1)")
    with_unknown = replace(SUBSET, forms=(*SUBSET.forms, cq.CensusForm("?.unknown", (("num",),))))
    assert reach([p], with_unknown).in_subset == 0


def test_end_forms_are_data_and_show_object_names_are_a_family() -> None:
    for text in ("result = 1", "show_object(shown)", "show_object(1 + 1)"):
        assert reach([program(text)], SUBSET).in_subset == 1
        assert reach([program(text)], replace(SUBSET, end_forms=())).in_subset == 0
    # Merely resembling the census's name or expression spellings is insufficient.
    parsed = census_program(program("show_object(shown)"))
    assert isinstance(parsed, ProgramCensus)
    for malformed in ("show_object()", "show_object(a.b)", "show_object(x)junk"):
        assert reach([parsed.model_copy(update={"end_form": malformed})], SUBSET).in_subset == 0


def test_reach_counts_unparsable_and_refuses_a_duplicate_stem() -> None:
    good, bad = program("result = 1", "a"), program("(", "b")
    assert reach([good, bad], SUBSET) == Reach(programs=2, in_subset=1, stems=("a",))
    assert reach([], SUBSET) == Reach(programs=0, in_subset=0, stems=())
    with pytest.raises(ValueError, match="stem"):
        reach([good, Unparsable(stem="a", kind="SyntaxError", message="bad")], SUBSET)


@pytest.mark.parametrize(
    ("total", "count", "stems"),
    [(-1, 0, ()), (1, -1, ()), (0, 1, ("a",)), (2, 1, ()), (2, 2, ("b", "a")), (2, 2, ("a", "a"))],
)
def test_reach_refuses_contradictory_counts_or_stems(
    total: int, count: int, stems: tuple[str, ...]
) -> None:
    with pytest.raises(ValidationError):
        Reach(programs=total, in_subset=count, stems=stems)


def test_records_and_nested_declarations_are_frozen() -> None:
    kinds = ["num"]
    positions = [kinds]
    keywords = [("height", kinds)]
    declaration = cq.CensusForm("a", positions, keywords)  # type: ignore[arg-type]
    forms = [declaration]
    selectors = [">Z"]
    ends = ["result = …"]
    subset = cq.Subset(forms, selectors, ends)  # type: ignore[arg-type]
    kinds.append("bool")
    positions.clear()
    keywords.clear()
    forms.clear()
    selectors.clear()
    ends.clear()
    assert subset.forms[0].positional == (("num",),)
    assert subset.forms[0].keywords == (("height", ("num",)),)
    assert subset.selectors == (">Z",)
    assert subset.end_forms == ("result = …",)
    with pytest.raises(FrozenInstanceError):
        subset.forms = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        declaration.name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        reach([], subset).programs = 1
    with pytest.raises(ValueError, match="keyword"):
        cq.CensusForm("a", keywords=(("x", ("num",)), ("x", ("str",))))
    with pytest.raises(ValueError, match="form"):
        cq.Subset((declaration, declaration))
    with pytest.raises(ValueError, match="selector"):
        cq.Subset((), selectors=(">Z", ">Z"))
    with pytest.raises(ValueError, match="end form"):
        cq.Subset((), end_forms=("empty", "empty"))


VALUES = {
    "str": "'XY'",
    "num": "2",
    "bool": "True",
    "none": "None",
    "tuple": "(0, 1)",
    "list": "[(0, 0), (1, 0), (0, 1)]",
    "call": "cq.Vector(0, 0, 0)",
    "name": "dimension",
    "expr": "dimension + 1",
}


@st.composite
def declared_programs(draw: st.DrawFn) -> tuple[CorpusProgram, cq.CensusForm]:
    chosen = draw(st.lists(st.sampled_from(SUBSET.forms), min_size=1, max_size=12))
    lines = ["import cadquery as cq", "dimension = 2", "wp = cq.Workplane('XY')"]
    for declaration in chosen:
        args = [
            VALUES[draw(st.sampled_from((*kinds, "name", "expr")))]
            for kinds in (slot or tuple(VALUES) for slot in declaration.positional)
        ]
        args += [
            f"{key}={VALUES[draw(st.sampled_from((*kinds, 'name', 'expr')))]}"
            for key, kinds in declaration.keywords
            if draw(st.booleans())
        ]
        callee = declaration.name.replace("Workplane.", "wp.")
        lines.append(f"{callee}({', '.join(args)})")
    lines.append("result = wp")
    return program("\n".join(lines)), draw(st.sampled_from(chosen))


@given(declared_programs())
def test_declared_forms_are_in_subset_and_removing_one_excludes_the_program(
    drawn: tuple[CorpusProgram, cq.CensusForm],
) -> None:
    p, removed = drawn
    assert reach([p], SUBSET).in_subset == 1
    reduced = replace(SUBSET, forms=tuple(f for f in SUBSET.forms if f != removed))
    assert reach([p], reduced).in_subset == 0


@given(st.lists(st.tuples(st.booleans(), st.text(max_size=40)), max_size=10))
def test_reach_order_and_json_round_trip(rows: list[tuple[bool, str]]) -> None:
    programs = [
        program("result = 1" if admitted else text, f"p{i}")
        for i, (admitted, text) in enumerate(rows)
    ]
    report = reach(programs, SUBSET)
    assert reach(reversed(programs), SUBSET) == report
    assert Reach.model_validate_json(report.model_dump_json()) == report


def test_all_300_slice_programs_are_in_subset_offline() -> None:
    root = fixture_cases.ROOT / "c1"
    data = gzip.decompress((root / "reach-programs.jsonl.gz").read_bytes())
    assert hashlib.sha256(data).hexdigest() == (
        "242c6a43bb55ac6bdcc692b90e5f5c295f54a1d03f3b1e7ad6c6a59d29fc45cb"
    )
    records = [json.loads(line) for line in data.splitlines()]
    rows = [ProgramCensus.model_validate(record["census"]) for record in records]
    stems = tuple(
        sorted(
            line
            for line in (root / "slice.txt").read_text().splitlines()
            if line and not line.startswith("#")
        )
    )
    assert len(stems) == 300
    assert tuple(sorted(row.stem for row in rows)) == stems
    assert all(
        record["source"] == "BenchCAD/BenchCAD" and record["licence"] == "CC-BY-4.0"
        for record in records
    )
    fidelity = json.loads((root / "fidelity.json").read_text())
    assert {record["census"]["stem"]: record["program_sha256"] for record in records} == {
        entry["name"]: entry["row"]["program_sha256"] for entry in fidelity["entries"]
    }
    assert reach(rows, SUBSET) == Reach(programs=300, in_subset=300, stems=stems)


def test_public_examples_run() -> None:
    assert doctest.testmod(_subset).failed == 0
    assert doctest.testmod(_reach).failed == 0


def test_programs_keep_the_existing_cadquery_namespace() -> None:
    text = """
import cadquery as cq
assert sorted(name for name in vars(cq) if not name.startswith('_')) == [
    'UnsupportedApi', 'Vector', 'Workplane'
]
assert cq.__name__ == 'arris_gym.cq'
try:
    cq._missing
except AttributeError:
    pass
else:
    raise AssertionError('private lookup changed')
# This module is mutable, as before; it is not a security boundary.
cq.metadata = 'a program may bind attributes'
assert cq.metadata == 'a program may bind attributes'
result = cq.Workplane('XY').box(1, 2, 3)
"""
    assert run(text, dialect="cq").status is Status.OK
    for name in ("subset", "Subset", "CensusForm"):
        got = run(f"import cadquery as cq\ncq.{name}()", dialect="cq")
        assert got.status is Status.UNSUPPORTED_API
        assert got.message == f"cq.{name}"


def test_decorators_copy_the_same_declaration_the_subset_reads() -> None:
    # Constructors build no model; their runtime and static literal checks
    # must agree, including bool's distinction from num.
    by_name = {form.name: form for form in cq.subset().forms}
    assert by_name["cq.Vector"] is vars(cq.Vector.__init__)["__census_form__"]
    assert by_name["cq.Workplane"] is vars(cq.Workplane.__init__)["__census_form__"]
    for value, kind in ((True, "bool"), (1, "num"), ("XY", "str"), (None, "none")):
        fits = SUBSET.admits(f"cq.Vector({kind}, num, num)")
        if fits:
            vector = cq.Vector(value, 0, 0)  # type: ignore[arg-type]
            assert vector.x == 1
        else:
            with pytest.raises(cq.UnsupportedApi):
                cq.Vector(value, 0, 0)  # type: ignore[arg-type]
