"""The package imports, and its pins are what SEED.md §7 says they are."""

import importlib.metadata
import pathlib
import tomllib

import arris_gym


def test_the_package_reports_its_version() -> None:
    assert arris_gym.__version__ == importlib.metadata.version("arris-gym")


def test_arris_and_numpy_are_pinned_exactly() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pins = {d.split("==")[0]: d.split("==")[1] for d in project["dependencies"] if "==" in d}
    assert pins["arris"] == importlib.metadata.version("arris")
    assert pins["numpy"] == importlib.metadata.version("numpy")
