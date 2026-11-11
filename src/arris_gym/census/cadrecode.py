"""Read CAD-Recode's pinned validation programs, lazily with the `[corpus]` extra.

Programs are untrusted text: this adapter reads them and never executes them.
The original CAD-Recode release is pinned by revision.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

from arris_gym.census._program import CorpusProgram
from arris_gym.census._report import CorpusInfo

REPO: Final = "filapro/cad-recode"
"""The authors' Hugging Face dataset repository."""
CONFIG: Final = "val"
"""The validation directory, with no training programs."""
REVISION: Final = "17d554bbc50a23de6cf6a742a3e0ed867f000153"
"""The immutable revision of the original release."""
LICENCE: Final = "CC-BY-NC-4.0"
"""The noncommercial licence of every derived row and artefact."""
PROGRAMS: Final = 968
"""The exact validation count at the pin; the dataset card says approximately 1k."""
INFO: Final = CorpusInfo(source=REPO, config=CONFIG, revision=REVISION, licence=LICENCE)
"""The source and licence attached to every census of this corpus."""


def download() -> list[Path]:
    """Fetch only validation Python files at the pin into the Hugging Face cache.

    Requires the network and `[corpus]`; the gate never calls this. Paths
    are sorted by their repository names. Listing the validation directory
    avoids traversing the million training files.

    >>> len(download())  # doctest: +SKIP
    968
    """
    from concurrent.futures import ThreadPoolExecutor

    from huggingface_hub import HfApi, hf_hub_download

    names = sorted(
        entry.path
        for entry in HfApi().list_repo_tree(
            REPO, path_in_repo=CONFIG, repo_type="dataset", revision=REVISION, recursive=True
        )
        if entry.path.endswith(".py")
    )
    if len(names) != PROGRAMS:
        raise ValueError(f"{len(names)} validation paths listed, {PROGRAMS} expected")

    def fetch(name: str) -> Path:
        return Path(hf_hub_download(REPO, name, repo_type="dataset", revision=REVISION))

    with ThreadPoolExecutor() as pool:
        return list(pool.map(fetch, names))


def read_files(paths: Sequence[Path], expected: int = PROGRAMS) -> list[CorpusProgram]:
    """Read validation Python as text, preserving file order and refusing a wrong count.

    Names are file stems, family is `validation` because the source has no
    family labels. Duplicate stems raise ValueError. Text is read as UTF-8,
    without newline translation, so its program hash names the source bytes.

    >>> from tempfile import TemporaryDirectory
    >>> with TemporaryDirectory() as directory:
    ...     path = Path(directory) / "0.py"
    ...     _ = path.write_text("r = 1", encoding="utf-8")
    ...     read_files([path], expected=1)[0].stem
    '0'
    """
    if len(paths) != expected:
        raise ValueError(f"{len(paths)} programs read, {expected} expected")
    stems = [path.stem for path in paths]
    if len(set(stems)) != len(stems):
        raise ValueError("a stem is used by more than one program")
    return [
        CorpusProgram(stem=path.stem, family="validation", text=path.read_bytes().decode("utf-8"))
        for path in paths
    ]


def read() -> list[CorpusProgram]:
    """Download and read the pinned validation corpus, refusing a different row count.

    Requires the network and the corpus extra.

    >>> len(read())  # doctest: +SKIP
    968
    """
    return read_files(download())
