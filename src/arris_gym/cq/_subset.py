"""The subset's declarations, shared by static reach and runtime checks (ADR-0012)."""

from __future__ import annotations

from dataclasses import dataclass

# A census cannot tell the value of a name, expression or call without running
# the program. These kinds may supply any runtime kind; literal kinds may not.
_DYNAMIC = ("name", "expr", "call")
_KINDS = ("str", "num", "bool", "none", "tuple", "list", *_DYNAMIC)


@dataclass(frozen=True)
class CensusForm:
    """One subset declaration: a call name, positional kinds and optional keywords.

    Each positional slot is a tuple of runtime kinds, or `None` for any
    runtime kind. Keywords are `(name, kinds)` pairs, sorted and unique;
    each is optional. Collections are copied to tuples, so a declaration
    stays frozen even when constructed from lists. Refuses duplicate keywords.
    `cq` uses stdlib frozen records to keep its dependency boundary.
    """

    name: str
    positional: tuple[tuple[str, ...] | None, ...] = ()
    keywords: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "positional", tuple(None if k is None else tuple(k) for k in self.positional)
        )
        object.__setattr__(
            self, "keywords", tuple(sorted((key, tuple(kinds)) for key, kinds in self.keywords))
        )
        keys = [key for key, _ in self.keywords]
        if len(set(keys)) != len(keys):
            raise ValueError("a keyword is declared twice")


def _parts(form: str) -> tuple[str, tuple[str, ...], tuple[tuple[str, str], ...]] | None:
    """Read a census API form; malformed or starred forms cannot be matched."""
    name, opening, rest = form.partition("(")
    if not opening or not rest.endswith(")"):
        return None
    inside = rest[:-1]
    before, separator, after = inside.partition("; ")
    if separator:
        positional = tuple(before.split(", "))
        named = after.split(", ")
    elif "=" in before:
        positional, named = (), before.split(", ")
    else:
        positional, named = tuple(before.split(", ")) if before else (), []
    keywords = tuple(item.partition("=")[::2] for item in named)
    if any(kind not in _KINDS for kind in positional):
        return None
    if any(not key.isidentifier() or kind not in _KINDS for key, kind in keywords):
        return None
    keys = [key for key, _ in keywords]
    if keys != sorted(set(keys)):
        return None
    return name, positional, keywords


def _fits(kind: str, allowed: tuple[str, ...] | None) -> bool:
    return allowed is None or (bool(allowed) and (kind in _DYNAMIC or kind in allowed))


@dataclass(frozen=True)
class Subset:
    """Frozen declarations of forms, selectors and end forms admitted by `cq`.

    Forms are sorted by name; duplicate declarations and selectors are
    refused. `show_object(…)` in `end_forms` also admits a named argument.
    This describes static reach, not successful execution: values and stack
    context are not decided by a census. Collections are copied to tuples.
    """

    forms: tuple[CensusForm, ...]
    selectors: tuple[str, ...] = ()
    end_forms: tuple[str, ...] = ("r = …", "result = …", "show_object(…)")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "forms",
            tuple(sorted(self.forms, key=lambda f: (f.name, repr(f.positional), repr(f.keywords)))),
        )
        object.__setattr__(self, "selectors", tuple(sorted(self.selectors)))
        object.__setattr__(self, "end_forms", tuple(sorted(self.end_forms)))
        if len(set(self.forms)) != len(self.forms):
            raise ValueError("a form is declared twice")
        if len(set(self.selectors)) != len(self.selectors):
            raise ValueError("a selector is declared twice")
        if len(set(self.end_forms)) != len(self.end_forms):
            raise ValueError("an end form is declared twice")

    def admits(self, form: str) -> bool:
        """Whether a census API form matches one declaration (ADR-0012).

        Literal kinds must fit; `name`, `expr` and `call` may have any runtime
        kind. Counts and keyword names must fit exactly. Starred arguments
        and malformed forms return False. No program is run.

        >>> from arris_gym.cq import subset
        >>> subset().admits("Workplane.box(num, name, expr)")
        True
        >>> subset().admits("Workplane.box(bool, num, num)")
        False
        """
        parts = _parts(form)
        if parts is None:
            return False
        name, positional, keywords = parts
        for declared in self.forms:
            if name != declared.name or len(positional) != len(declared.positional):
                continue
            if not all(
                _fits(kind, allowed)
                for kind, allowed in zip(positional, declared.positional, strict=True)
            ):
                continue
            allowed_keywords = dict(declared.keywords)
            if all(
                key in allowed_keywords and _fits(kind, allowed_keywords[key])
                for key, kind in keywords
            ):
                return True
        return False


def subset() -> Subset:
    """The current `cq` subset, read from the declarations its decorators enforce.

    No model is built. Removing a form from this record changes only a
    caller's reach calculation, never the runtime subset.

    >>> from arris_gym.cq import subset
    >>> len(subset().forms), subset().selectors
    (15, ())
    """
    from arris_gym.cq._vector import Vector
    from arris_gym.cq._workplane import Workplane

    forms = []
    for cls in (Vector, Workplane):
        for method in vars(cls).values():
            declared = getattr(method, "__census_form__", None)
            if isinstance(declared, CensusForm):
                forms.append(declared)
    return Subset(forms=tuple(forms))
