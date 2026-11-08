"""What a `cq` program's result resolves to: one `arris.build.Solid` (ADR-0007).

Called by the program worker (`sandbox/_program.py`) after the program ran,
on the last `show_object` argument or, failing one, the module-level
`result`. Private.
"""

from __future__ import annotations

import arris.build

from arris_gym.cq._unsupported import UnsupportedApi
from arris_gym.cq._workplane import Workplane


class NotASolid(Exception):
    """The program's result is not a `Workplane` holding a solid.

    The message says what it is instead. The sandbox decides the status
    `runtime` from this type alone.
    """


def solid_of(value: object, where: str) -> arris.build.Solid:
    """The single solid on `value`'s stack; `where` names `value` in a message.

    Raises `NotASolid` when `value` is not a `Workplane` or its stack holds
    no solid, and `UnsupportedApi` naming the count when it holds several:
    a CadQuery compound is outside the subset.
    """
    if not isinstance(value, Workplane):
        raise NotASolid(f"{where} is of type {type(value).__name__}, not cadquery.Workplane")
    solids = value._solids()
    if not solids:
        raise NotASolid(f"{where} is a Workplane holding no solid")
    if len(solids) > 1:
        raise UnsupportedApi(f"a Workplane holding {len(solids)} solids")
    return solids[0]
