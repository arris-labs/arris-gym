"""`dump_text` and `digest`: a result as text, and a corpus as one hash.

A result is written as one line per field, each value on its own line and
strings JSON-quoted so none spans lines. `digest` is the SHA-256 of those
lines with every float in hex (`float.hex`, exact), rows in program order.
`seconds` is wall-clock and is in neither: it is not a result. Private; the
public names are re-exported by `arris_gym`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable

from arris_gym.sandbox.outcome import ExecResult, Measures

Number = Callable[[float], str]


def _string(value: str) -> str:
    return json.dumps(value)  # ASCII-escaped: one line, the same bytes everywhere


def _strings(values: Iterable[str]) -> str:
    return "[" + ", ".join(_string(v) for v in values) + "]"


def _vector(values: Iterable[float], number: Number) -> str:
    return "[" + ", ".join(number(v) for v in values) + "]"


def _measure_lines(measures: Measures, number: Number) -> list[str]:
    low, high = measures.bounds
    kinds = ", ".join(f"[{_string(kind)}, {count}]" for kind, count in measures.face_kinds)
    return [
        f"measures.volume: {number(measures.volume)}",
        f"measures.area: {number(measures.area)}",
        f"measures.centroid: {_vector(measures.centroid, number)}",
        f"measures.bounds: [{_vector(low, number)}, {_vector(high, number)}]",
        f"measures.faces: {measures.faces}",
        f"measures.shells: {measures.shells}",
        f"measures.genus: {measures.genus}",
        f"measures.face_kinds: [{kinds}]",
    ]


def _lines(result: ExecResult, number: Number) -> list[str]:
    lines = [f"status: {result.status.value}", f"message: {_string(result.message)}"]
    if result.refusal is None:
        lines.append("refusal: none")
    else:
        lines += [
            f"refusal.kind: {_string(result.refusal.kind)}",
            f"refusal.message: {_string(result.refusal.message)}",
            f"refusal.entities: {_strings(result.refusal.entities)}",
        ]
    lines.append("body: none" if result.body is None else f"body: {result.body.sha256}")
    if result.measures is None:
        lines.append("measures: none")
    else:
        lines += _measure_lines(result.measures, number)
    lines += [
        f"violations: {_strings(result.violations)}",
        f"program_sha256: {result.program_sha256}",
        f"dialect: {result.dialect.value}",
        f"versions: arris={_string(result.versions.arris)}"
        f" numpy={_string(result.versions.numpy)}"
        f" arris_gym={_string(result.versions.arris_gym)}",
    ]
    return lines


def dump_text(result: ExecResult) -> str:
    """The result as text, a line per field, for a person to read or `diff`.

    Everything but `seconds`. Floats are Python's shortest exact `repr`; the
    same result always gives the same text.

    >>> import arris_gym as ag
    >>> print(ag.dump_text(ag.run("result = (")).splitlines()[0])
    status: syntax
    """
    return "\n".join(_lines(result, repr)) + "\n"


def digest(results: Iterable[ExecResult]) -> str:
    """The SHA-256 (hex) of `results` in the order given: the determinism check.

    Each row contributes everything `dump_text` shows, with floats in hex so
    that a one-bit change of a measure moves it; `seconds` is excluded. The
    order matters: the same results in another order digest differently.

    >>> import arris_gym as ag
    >>> rows = ag.run_many(["result = (", "x = 1"])
    >>> ag.digest(rows) == ag.digest(ag.run_many(["result = (", "x = 1"]))
    True
    """
    hasher = hashlib.sha256()
    for result in results:
        for line in _lines(result, float.hex):
            hasher.update(line.encode("ascii"))
            hasher.update(b"\n")
        hasher.update(b"--\n")
    return hasher.hexdigest()
