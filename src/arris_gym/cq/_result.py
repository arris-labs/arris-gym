"""What a `cq` program's result resolves to: one `arris.build.Solid` (ADR-0007).

A CadQuery compound is that one solid, its body holding a shell per piece
(ADR-0016).

Called by the program worker (`sandbox/_program.py`) after the program ran,
on the last `show_object` argument, else the module-level `result`, else
module-level `r` (ADR-0015). Private.
"""

from __future__ import annotations

import arris.build

from arris_gym.cq._workplane import Workplane


class NotASolid(Exception):
    """The program's result is not a `Workplane` holding a solid.

    The message says what it is instead. The sandbox decides the status
    `runtime` from this type alone.
    """


def solid_of(value: object, where: str) -> arris.build.Solid:
    """The solid on `value`'s stack; `where` names `value` in a message.

    A compound is one such solid, its body holding a shell per piece
    (ADR-0016). Raises `NotASolid` when `value` is not a `Workplane` or its
    stack holds no solid.
    """
    if not isinstance(value, Workplane):
        raise NotASolid(f"{where} is of type {type(value).__name__}, not cadquery.Workplane")
    solids = value._solids()
    if not solids:
        raise NotASolid(f"{where} is a Workplane holding no solid")
    return solids[0]
