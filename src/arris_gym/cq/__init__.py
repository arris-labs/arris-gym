"""The CadQuery-compatible subset over arris.build. Imports only arris.

Inside a program worker of the `cq` dialect its CadQuery names are installed
as `cadquery` (ADR-0007, ADR-0012); a name the **subset** lacks
raises `UnsupportedApi` naming it (`cq.Sketch`), never `AttributeError`.
Callers also get `subset`, `Subset` and `CensusForm` as static metadata.

>>> import arris_gym.cq as cq
>>> try:
...     cq.Sketch()
... except cq.UnsupportedApi as error:
...     print(error)
cq.Sketch
"""

# `subset`, `Subset` and `CensusForm` describe the subset to callers. They do
# not declare CadQuery forms of their own.
from typing import NoReturn as _NoReturn

from arris_gym.cq._subset import CensusForm, Subset, subset
from arris_gym.cq._unsupported import UnsupportedApi
from arris_gym.cq._unsupported import is_python_name as _is_python_name
from arris_gym.cq._vector import Vector
from arris_gym.cq._workplane import Workplane

__all__ = ["CensusForm", "Subset", "UnsupportedApi", "Vector", "Workplane", "subset"]


def __getattr__(name: str) -> _NoReturn:
    if _is_python_name(name):
        raise AttributeError(name)
    raise UnsupportedApi(f"cq.{name}")
