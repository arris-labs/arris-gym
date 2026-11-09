"""The BenchCAD adapter: the slice's programs and their committed targets (ADR-0011).

Reads the pinned corpus through `census.benchcad` (the `[corpus]` extra, the
network once) and the slice and targets files that sit in the repository, so
the entries depend on nothing else. The programs are model-written:
untrusted, run only in a sandbox worker.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from pathlib import Path
from typing import Final

from arris_gym.census import CorpusProgram, benchcad
from arris_gym.rescore._table import RescoreEntry
from arris_gym.sandbox.outcome import Dialect

SLICE: Final = Path("tests/fixtures/c1/slice.txt")
"""The default slice file: one stem per line, `#` lines are the header."""
TARGETS: Final = Path("tests/fixtures/c1/targets.jsonl.gz")
"""The default targets file: stem, `step_sha256`, STEP text, gzipped, by stem."""


def read_stems(path: Path) -> list[str]:
    """The stems of a slice file: one per line, `#` lines are its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def read_targets(path: Path) -> dict[str, str]:
    """The STEP text of each stem in a targets file (`.jsonl.gz`)."""
    text = gzip.decompress(path.read_bytes()).decode("utf-8")
    return {row["stem"]: row["step"] for row in map(json.loads, text.splitlines())}


def entries(
    stems: list[str],
    targets: dict[str, str],
    programs: list[CorpusProgram],
) -> list[RescoreEntry]:
    """The entries of `stems` in order: each program (dialect `cq`) with its target.

    Raises `ValueError` for a stem the targets or the corpus lack, or lists
    twice: that is not the slice, and no program is at fault.
    """
    if len(set(stems)) != len(stems):
        raise ValueError("a stem is listed twice")
    by_stem = {p.stem: p for p in programs}
    for stem in stems:
        if stem not in targets:
            raise ValueError(f"no target for stem {stem!r}")
        if stem not in by_stem:
            raise ValueError(f"stem {stem!r} is not in the pinned corpus")
    return [
        RescoreEntry(
            name=stem,
            source=f"{benchcad.REPO} ({benchcad.CONFIG})",
            licence=benchcad.LICENCE,
            program=by_stem[stem].text,
            dialect=Dialect.CQ,
            step=targets[stem],
        )
        for stem in stems
    ]


Reader = Callable[[], list[CorpusProgram]]


def load(
    slice_path: Path, targets_path: Path, reader: Reader = benchcad.read
) -> list[RescoreEntry]:
    """The slice's entries: `reader`'s programs, the targets file's STEPs."""
    return entries(read_stems(slice_path), read_targets(targets_path), reader())
