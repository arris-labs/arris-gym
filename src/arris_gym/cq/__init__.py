"""The CadQuery-compatible subset over arris.build. Imports only arris.

Inside a program worker of the `cq` dialect this module is `cadquery`
(ADR-0007): `import cadquery as cq` gets it, and a name the **subset** lacks
raises `UnsupportedApi` naming it (`cq.Sketch`), never `AttributeError`.

>>> import arris_gym.cq as cq
>>> try:
...     cq.Sketch()
... except cq.UnsupportedApi as error:
...     print(error)
cq.Sketch
"""

# Every public name here is one a program sees as `cq.<name>`: what is not
# CadQuery's is imported under a private one.
from typing import NoReturn as _NoReturn

from arris_gym.cq._unsupported import UnsupportedApi
from arris_gym.cq._unsupported import is_python_name as _is_python_name
from arris_gym.cq._vector import Vector
from arris_gym.cq._workplane import Workplane

__all__ = ["UnsupportedApi", "Vector", "Workplane"]


def __getattr__(name: str) -> _NoReturn:
    if _is_python_name(name):
        raise AttributeError(name)
    raise UnsupportedApi(f"cq.{name}")
