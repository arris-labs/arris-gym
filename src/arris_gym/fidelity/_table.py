"""The fidelity table and the consumer report for arris.

`fidelity_table` gathers the rows of a corpus (or of the fixtures) under their
program names: sorted by name, so the digest does not depend on the order the
rows arrived in, and counted over every row, the failures and timeouts
included. `arris_rows` takes from a table what arris's maintainers act on: a
histogram of the refusals by kind and then reason, and the arris bugs with
their program SHA-256 and regression fixture (ADR-0006). Each entry carries its
program's source and licence, and the report the licences and versions of all
the rows.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from typing import Any, Self

import pydantic
from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.fidelity._compare import (
    DisagreementClass,
    FidelityOutcome,
    FidelityRow,
    RegressionFixture,
)
from arris_gym.fidelity._oracle import OracleStatus, OracleVersions
from arris_gym.sandbox import Status

_CONFIG = ConfigDict(frozen=True, extra="forbid")

Counts = dict[str, int]
"""A count per name, every member of the enumeration present (zero included)."""


class TableEntry(BaseModel):
    """One program's fidelity row under the program's name (a stem, a fixture),
    with where the program came from (`source`) and its `licence`, as every row
    carries them (gym.md, Data). Both are the caller's, never empty."""

    model_config = _CONFIG

    name: str = pydantic.Field(min_length=1)
    source: str = pydantic.Field(min_length=1)
    licence: str = pydantic.Field(min_length=1)
    row: FidelityRow


def _counts(names: list[str], members: list[str]) -> Counts:
    seen = Counter(names)
    return {member: seen[member] for member in members}


class FidelityTable(BaseModel):
    """The rows of a corpus against the oracle, with counts over all of them.

    Guarantees, all validated: `entries` are sorted by name, each name once;
    `programs` is `len(entries)` and every count is over `programs`, so a
    program that failed or timed out is in each denominator; `outcomes`,
    `classes`, `statuses` and `oracle_statuses` hold every member of their
    enumeration, zero included, and add up to `programs` (`classes` to the
    disagreements); `timed_out` names, sorted, each program that timed out on
    either side; `digest` is the SHA-256 of the table's canonical JSON
    without the digest field (sorted keys, no whitespace, ASCII).
    """

    model_config = _CONFIG

    entries: tuple[TableEntry, ...]
    programs: int
    outcomes: Counts
    classes: Counts
    statuses: Counts
    oracle_statuses: Counts
    timed_out: tuple[str, ...]
    digest: str

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        names = [entry.name for entry in self.entries]
        if names != sorted(set(names)):
            raise ValueError("entries are not sorted by name, or a name is listed twice")
        fields = _fields(self.entries)
        for key, value in fields.items():
            if getattr(self, key) != value:
                raise ValueError(f"{key} is not that of the entries")
        if self.digest != _digest(self.model_dump(mode="json")):
            raise ValueError("digest is not that of the table's content")
        return self

    def to_json(self) -> str:
        """The table as canonical JSON, digest included: `from_json` returns an equal table."""
        return _canonical(self.model_dump(mode="json"))

    @classmethod
    def from_json(cls, text: str) -> Self:
        """Read a table written by `to_json`; refuses one whose digest or counts do not match."""
        return cls.model_validate(json.loads(text))


def _fields(entries: Iterable[TableEntry]) -> dict[str, Any]:
    rows = list(entries)
    return {
        "programs": len(rows),
        "outcomes": _counts(
            [e.row.outcome.value for e in rows], [o.value for o in FidelityOutcome]
        ),
        "classes": _counts(
            [e.row.disagreement.value for e in rows if e.row.disagreement is not None],
            [c.value for c in DisagreementClass],
        ),
        "statuses": _counts([e.row.status.value for e in rows], [s.value for s in Status]),
        "oracle_statuses": _counts(
            [e.row.oracle_status.value for e in rows], [s.value for s in OracleStatus]
        ),
        "timed_out": tuple(e.name for e in rows if e.row.timed_out),
    }


def _canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(data: dict[str, Any]) -> str:
    body = {key: value for key, value in data.items() if key != "digest"}
    return hashlib.sha256(_canonical(body).encode("ascii")).hexdigest()


def fidelity_table(entries: Iterable[TableEntry]) -> FidelityTable:
    """The table of `entries`, sorted by name, counted over all of them.

    The order they are given in does not move the table or its digest. Raises
    `ValueError` for a name given twice: two rows under one name cannot be
    told apart in a report.

    >>> fidelity_table([]).programs
    0
    """
    ordered = tuple(sorted(entries, key=lambda e: e.name))
    fields = _fields(ordered)
    draft = FidelityTable.model_construct(entries=ordered, digest="", **fields)
    return FidelityTable(entries=ordered, digest=_digest(draft.model_dump(mode="json")), **fields)


class ArrisReason(BaseModel):
    """One refusal message, verbatim, and how many rows carry it."""

    model_config = _CONFIG

    reason: str
    count: int = pydantic.Field(ge=1)


class ArrisRefusalKind(BaseModel):
    """The refusals of one exception class: `count` is the sum of `reasons`'
    counts, the reasons sorted by message."""

    model_config = _CONFIG

    kind: str
    count: int = pydantic.Field(ge=1)
    reasons: tuple[ArrisReason, ...]


class ArrisBug(BaseModel):
    """A program on which arris is wrong: the program's name and SHA-256, how both
    sides ended, and the `tests/fixtures/regression/` directory that holds the case
    (`None` while the row has no fixture)."""

    model_config = _CONFIG

    name: str
    program_sha256: str
    status: Status
    oracle_status: OracleStatus
    fixture: str | None


def _oracle_key(v: OracleVersions) -> tuple[str, str, str]:
    return (v.cadquery, v.ocp, v.python)


class ArrisReport(BaseModel):
    """What the fidelity table tells arris: the refusals by kind then reason, and the bugs.

    `programs` is the table's whole denominator, not the rows listed. The
    refusals are those rows classed `arris_refusal`, with the kernel's own
    words; kinds are sorted by kind, bugs by name. `licences`,
    `arris_versions`, `numpy_versions` and `oracle_versions` are those of
    every row of the table, each distinct and sorted (validated; the oracle's
    by cadquery, OCP, Python), so the report states its licence and what it
    was produced under; a row whose oracle never answered adds no oracle
    version.
    """

    model_config = _CONFIG

    programs: int
    licences: tuple[str, ...]
    arris_versions: tuple[str, ...]
    numpy_versions: tuple[str, ...]
    oracle_versions: tuple[OracleVersions, ...]
    refusals: tuple[ArrisRefusalKind, ...]
    bugs: tuple[ArrisBug, ...]

    @model_validator(mode="after")
    def _sorted(self) -> Self:
        for key in ("licences", "arris_versions", "numpy_versions"):
            values: tuple[str, ...] = getattr(self, key)
            if list(values) != sorted(set(values)):
                raise ValueError(f"{key} are not distinct and sorted")
        keys = [_oracle_key(v) for v in self.oracle_versions]
        if keys != sorted(set(keys)):
            raise ValueError("oracle_versions are not distinct and sorted")
        return self

    def to_json(self) -> str:
        """The report as canonical JSON."""
        return _canonical(self.model_dump(mode="json"))

    def to_markdown(self) -> str:
        """The report as Markdown: the refusal histogram, then the bug list."""
        lines = [
            "# arris report",
            "",
            f"Over {self.programs} programs: "
            f"{sum(k.count for k in self.refusals)} arris refusals, {len(self.bugs)} arris bugs.",
            "",
            f"Licences: {', '.join(self.licences) or 'none'}.",
            f"arris {', '.join(self.arris_versions) or 'none'}; "
            f"numpy {', '.join(self.numpy_versions) or 'none'}; oracle "
            + (
                ", ".join(
                    f"cadquery {v.cadquery}, OCP {v.ocp}, Python {v.python}"
                    for v in self.oracle_versions
                )
                or "none"
            )
            + ".",
            "",
            "## Refusals",
            "",
        ]
        if not self.refusals:
            lines += ["None.", ""]
        for kind in self.refusals:
            lines += [f"### {kind.kind} ({kind.count})", ""]
            lines += [f"- {reason.count}x `{reason.reason}`" for reason in kind.reasons]
            lines.append("")
        lines += ["## Bugs", ""]
        if not self.bugs:
            lines += ["None.", ""]
        for bug in self.bugs:
            lines.append(
                f"- `{bug.name}` ({bug.program_sha256}): arris {bug.status.value}, "
                f"oracle {bug.oracle_status.value}, fixture {bug.fixture or 'none'}"
            )
        return "\n".join(lines).rstrip("\n") + "\n"


def arris_rows(table: FidelityTable) -> ArrisReport:
    """The arris-facing report of a table: refusals by kind then reason, and arris bugs.

    A refusal is in the histogram when its row is classed `arris_refusal`
    (a row re-classed by a verdict is the verdict's class and is not). An arris bug's
    fixture is its verdict's `RegressionFixture`, if any.

    >>> arris_rows(fidelity_table([])).programs
    0
    """
    reasons: dict[str, Counter[str]] = {}
    bugs: list[ArrisBug] = []
    for entry in table.entries:
        row = entry.row
        if row.disagreement is DisagreementClass.ARRIS_REFUSAL and row.refusal is not None:
            reasons.setdefault(row.refusal.kind, Counter())[row.refusal.message] += 1
        elif row.disagreement is DisagreementClass.ARRIS_BUG:
            evidence = row.verdict.evidence if row.verdict is not None else None
            bugs.append(
                ArrisBug(
                    name=entry.name,
                    program_sha256=row.program_sha256,
                    status=row.status,
                    oracle_status=row.oracle_status,
                    fixture=evidence.path if isinstance(evidence, RegressionFixture) else None,
                )
            )
    kinds = tuple(
        ArrisRefusalKind(
            kind=kind,
            count=sum(counter.values()),
            reasons=tuple(ArrisReason(reason=r, count=counter[r]) for r in sorted(counter)),
        )
        for kind, counter in sorted(reasons.items())
    )
    rows = [entry.row for entry in table.entries]
    oracle = {_oracle_key(r.oracle_versions): r.oracle_versions for r in rows if r.oracle_versions}
    return ArrisReport(
        programs=table.programs,
        licences=tuple(sorted({entry.licence for entry in table.entries})),
        arris_versions=tuple(sorted({r.versions.arris for r in rows})),
        numpy_versions=tuple(sorted({r.versions.numpy for r in rows})),
        oracle_versions=tuple(oracle[key] for key in sorted(oracle)),
        refusals=kinds,
        bugs=tuple(bugs),
    )
