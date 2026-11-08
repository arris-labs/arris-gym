"""API forms: a call's arguments checked against the census's form for it.

ADR-0007. A call the subset implements still refuses an argument form the
census does not write, as `UnsupportedApi` naming the form the census's way
(`Workplane.box(num, num, num; centered=bool)`), never as `TypeError`.
Private.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from typing import Concatenate

from arris_gym.cq._unsupported import UnsupportedApi

__all__ = ["census_form", "kind_of", "numbers_of", "shape_of"]

# What the census writes for an argument that is itself a call's value: a
# `Vector(...)` or a `Workplane` is a "call" there, whatever it holds. Told by
# class name, since `Vector` itself decorates its constructor with this module.
_CALL = "call"
_CALL_CLASSES = ("Vector", "Workplane")


def kind_of(value: object) -> str:
    """The census's kind of a runtime value: `num`, `bool`, `str`, `none`, `tuple`,
    `list` or `call` (a `Vector` or a `Workplane`); any other value is its type's name.

    >>> kind_of(1.5), kind_of(True), kind_of((1, 2)), kind_of({})
    ('num', 'bool', 'tuple', 'dict')
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "num"
    if isinstance(value, str):
        return "str"
    if value is None:
        return "none"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, list):
        return "list"
    if type(value).__name__ in _CALL_CLASSES:
        return _CALL
    return type(value).__name__


def _form_text(name: str, args: Sequence[object], kwargs: Mapping[str, object]) -> str:
    """`name(kind, ...; keyword=kind, ...)`, keywords sorted: the census's spelling."""
    positional = ", ".join(kind_of(a) for a in args)
    named = ", ".join(f"{k}={kind_of(v)}" for k, v in sorted(kwargs.items()))
    inside = f"{positional}; {named}" if positional and named else positional or named
    return f"{name}({inside})"


def census_form[**P, R, S](
    name: str,
    positional: Sequence[Sequence[str] | None] = (),
    keywords: Mapping[str, Sequence[str]] | None = None,
) -> Callable[[Callable[Concatenate[S, P], R]], Callable[Concatenate[S, P], R]]:
    """Decorate a method so that only the census's form of it runs.

    `positional` holds, for each positional argument, the kinds it may be
    (`None` for any); the call must give exactly that many. `keywords` maps
    each keyword the call may give to the kinds it may be; any subset of
    them is accepted, in any order. Any other form raises `UnsupportedApi`
    naming it, before the method runs.
    """
    allowed = dict(keywords or {})

    def decorate(
        method: Callable[Concatenate[S, P], R],
    ) -> Callable[Concatenate[S, P], R]:
        @functools.wraps(method)
        def checked(self: S, /, *args: P.args, **kwargs: P.kwargs) -> R:
            fits = len(args) == len(positional) and all(
                kinds is None or kind_of(arg) in kinds
                for arg, kinds in zip(args, positional, strict=True)
            )
            fits = fits and all(
                key in allowed and kind_of(value) in allowed[key] for key, value in kwargs.items()
            )
            if not fits:
                raise UnsupportedApi(_form_text(name, args, kwargs))
            return method(self, *args, **kwargs)

        return checked

    return decorate


def shape_of(value: object) -> str:
    """What `value` is for a message: `3 numbers` for a tuple or list of numbers,
    `tuple of non-numbers` for one of other things, else its kind.

    >>> shape_of((1, 2, 3)), shape_of("a"), shape_of([1, "a"])
    ('3 numbers', 'str', 'list of non-numbers')
    """
    kind = kind_of(value)
    if isinstance(value, tuple | list):
        if all(kind_of(n) == "num" for n in value):
            return f"{len(value)} numbers"
        return f"{kind} of non-numbers"
    return kind


def numbers_of(value: object, count: Sequence[int]) -> tuple[float, ...] | None:
    """`value` as floats when it is a tuple or list of `count` numbers, else `None`.

    >>> numbers_of((1, 2), (2, 3)), numbers_of((1, 2, 3, 4), (2, 3))
    ((1.0, 2.0), None)
    """
    if (
        isinstance(value, tuple | list)
        and len(value) in count
        and all(kind_of(n) == "num" for n in value)
    ):
        return tuple(float(n) for n in value)
    return None
