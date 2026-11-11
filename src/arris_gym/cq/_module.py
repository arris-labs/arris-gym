"""The program-facing CadQuery names, apart from caller metadata (ADR-0012)."""

from types import ModuleType
from typing import NoReturn

from arris_gym.cq._unsupported import UnsupportedApi, is_python_name
from arris_gym.cq._vector import Vector
from arris_gym.cq._workplane import Workplane


class _Cadquery(ModuleType):
    def __getattr__(self, name: str) -> NoReturn:
        if is_python_name(name):
            raise AttributeError(name)
        raise UnsupportedApi(f"cq.{name}")


def program_module() -> ModuleType:
    """A module exposing the existing CadQuery names, for installation in a worker.

    This is API presentation, not an isolation boundary: a program may
    mutate this module and introspect its process as before.
    """
    module = _Cadquery("arris_gym.cq")
    # Package lookup must still reach the worker's _NoCadquerySubmodule finder
    # so `import cadquery.occ_impl` keeps its typed refusal.
    module.__path__ = []
    module.UnsupportedApi = UnsupportedApi  # type: ignore[attr-defined]
    module.Vector = Vector  # type: ignore[attr-defined]
    module.Workplane = Workplane  # type: ignore[attr-defined]
    return module
