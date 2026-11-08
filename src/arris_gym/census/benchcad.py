"""Reading BenchCAD's `code_gen` programs at the pinned revision (ADR-0003).

Needs the optional `[corpus]` extra (`huggingface-hub`, `pyarrow`), imported
lazily: `import arris_gym` and `import arris_gym.census` need neither. The
programs read here are model-written: untrusted, parsed by the census and
never run outside a sandbox worker.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

from arris_gym.census._program import CorpusProgram
from arris_gym.census._report import CorpusInfo

REPO: Final = "BenchCAD/BenchCAD"
"""The Hugging Face dataset repository."""
CONFIG: Final = "code_gen"
"""The configuration read: the image-to-code programs."""
REVISION: Final = "5919f578ab09ec283603a082fab07c7639ab56eb"
"""The pinned revision; a corpus is never read at a moving branch."""
LICENCE: Final = "CC-BY-4.0"
"""The corpus's licence; weights and rows made from it inherit its attribution."""
PROGRAMS: Final = 17_900
"""The pinned corpus's row count; any other count is not the pinned corpus."""
COLUMNS: Final = ("stem", "family", "code")
"""The only columns read: the parquet files also hold images."""

INFO: Final = CorpusInfo(source=REPO, config=CONFIG, revision=REVISION, licence=LICENCE)
"""What every census of this corpus records about it."""


def download() -> list[Path]:
    """Fetch `code_gen`'s parquet files at the pinned revision into the Hugging Face cache.

    Needs the network and the `[corpus]` extra; the gate never calls it.
    Returns the files sorted by name.
    """
    from huggingface_hub import snapshot_download

    root = Path(
        snapshot_download(
            repo_id=REPO,
            repo_type="dataset",
            revision=REVISION,
            allow_patterns=[f"{CONFIG}/data/*.parquet"],
        )
    )
    return sorted((root / CONFIG / "data").glob("*.parquet"))


def read_parquet(paths: Sequence[Path], expected: int = PROGRAMS) -> list[CorpusProgram]:
    """The programs of parquet files, only the `stem`, `family` and `code` columns.

    Files are read in the order given and rows in file order. Raises
    `ValueError` when the row count is not `expected` or a cell is not a
    string: that is not the pinned corpus, and no program is at fault.
    """
    import pyarrow.parquet as pq

    programs: list[CorpusProgram] = []
    for path in paths:
        for batch in pq.ParquetFile(path).iter_batches(columns=list(COLUMNS)):
            columns = [batch.column(name).to_pylist() for name in COLUMNS]
            for stem, family, code in zip(*columns, strict=True):
                if not all(isinstance(cell, str) for cell in (stem, family, code)):
                    raise ValueError(f"{path.name}: a stem, family or code cell is not a string")
                programs.append(CorpusProgram(stem=stem, family=family, text=code))
    if len(programs) != expected:
        raise ValueError(
            f"{len(programs)} programs read, {expected} expected: not the pinned corpus"
        )
    return programs


def read() -> list[CorpusProgram]:
    """BenchCAD's `code_gen` programs at the pinned revision: `download`, then `read_parquet`."""
    return read_parquet(download())
