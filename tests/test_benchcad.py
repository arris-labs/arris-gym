"""The BenchCAD reader reads three columns and refuses a corpus that is not the pinned one."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from arris_gym.census import CorpusProgram, benchcad


def write(path: Path, rows: list[tuple[str, str, str]], *, extra: bool = True) -> Path:
    table = {
        "image": [b"\x89PNG" for _ in rows],
        "code": [code for _, _, code in rows],
        "family": [family for _, family, _ in rows],
        "stem": [stem for stem, _, _ in rows],
    }
    if not extra:
        del table["image"]
    pq.write_table(pa.table(table), path)
    return path


ROWS = [("b", "gear", "x = 1"), ("a", "washer", "y = 2"), ("c", "gear", "(")]


def test_the_three_columns_are_read_in_file_order(tmp_path: Path) -> None:
    got = benchcad.read_parquet([write(tmp_path / "0.parquet", ROWS)], expected=3)
    assert got == [
        CorpusProgram(stem="b", family="gear", text="x = 1"),
        CorpusProgram(stem="a", family="washer", text="y = 2"),
        CorpusProgram(stem="c", family="gear", text="("),
    ]


def test_several_files_are_read_in_the_order_given(tmp_path: Path) -> None:
    first = write(tmp_path / "1.parquet", ROWS[:1], extra=False)
    second = write(tmp_path / "0.parquet", ROWS[1:])
    got = benchcad.read_parquet([first, second], expected=3)
    assert [p.stem for p in got] == ["b", "a", "c"]


def test_a_row_count_other_than_the_pinned_one_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "0.parquet", ROWS)
    with pytest.raises(ValueError, match=r"3 programs read, 17900 expected"):
        benchcad.read_parquet([path])
    with pytest.raises(ValueError, match="2 expected"):
        benchcad.read_parquet([path], expected=2)


def test_a_cell_that_is_not_a_string_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "0.parquet"
    pq.write_table(pa.table({"stem": ["a"], "family": ["f"], "code": [None]}), path)
    with pytest.raises(ValueError, match="not a string"):
        benchcad.read_parquet([path], expected=1)


def test_the_corpus_is_pinned() -> None:
    assert benchcad.INFO.revision == "5919f578ab09ec283603a082fab07c7639ab56eb"
    assert (benchcad.INFO.config, benchcad.INFO.licence) == ("code_gen", "CC-BY-4.0")
    assert benchcad.PROGRAMS == 17_900
