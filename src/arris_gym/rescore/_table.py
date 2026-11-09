"""The re-scored table: a row per program, aggregates over all of them (ADR-0011).

docs/ARCHITECTURE.md §The re-scored table. Every program has a row and every
aggregate states its denominator; the digest is the table's identity across
machines and depends on no wall-clock time and no input order.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.fidelity._table import _code
from arris_gym.reward import IouRoute, Score, invalidity_rate
from arris_gym.sandbox.outcome import ArrisRefusal, Dialect, Status, Versions

# The statuses a scoring or target failure can give: the scorer failing
# never pays, so these are the failure statuses of a pair, not a program's.
_PAIR_FAILURES: Final = frozenset({Status.RUNTIME, Status.TIMEOUT, Status.CRASH})


class Stage(StrEnum):
    """Where a program's failure happened, if it did (ADR-0011).

    `Score` carries a status but not the stage that decided it: a target
    that could not be read and a scoring that crashed both end a failure
    status, and a table must tell them from the program's own.
    """

    NONE = "none"
    """No failure: the program ran and the pair was scored."""
    PROGRAM = "program"
    """The program did not end `ok`: its status is the score's."""
    TARGET = "target"
    """The program ran, but its target could not be read into a valid body."""
    SCORING = "scoring"
    """Both bodies are valid, but scoring the pair failed."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _is_sha256(text: str) -> bool:
    return len(text) == hashlib.sha256().digest_size * 2 and all(
        c in "0123456789abcdef" for c in text
    )


class RescoreEntry(_Frozen):
    """One program to re-score: its identity, text, dialect and target STEP.

    `source` and `licence` travel into the row, so a score is never
    separated from the licence of its data. Refuses an empty `name`.
    """

    name: str
    source: str
    licence: str
    program: str
    dialect: Dialect
    step: str

    @model_validator(mode="after")
    def _named(self) -> Self:
        if not self.name:
            raise ValueError("an entry has a name")
        return self


class RescoreRow(_Frozen):
    """What re-scoring one program gave: statuses, digests and the `Score`.

    `program_status` and `program_refusal` are the program's own; `stage` is
    where a failure happened. Guarantees, enforced on construction: `stage`
    is `none` exactly when the score is `ok`, and then the program is `ok`;
    `program` means the program is not `ok` and the score has its status;
    `target` and `scoring` mean the program is `ok` and the score ended
    `runtime`, `timeout` or `crash`; `program_refusal` is set exactly when
    the program ended `arris_refusal`; every digest is a hex SHA-256. A
    `none` or `scoring` row has both body digests, a `target` row has the
    candidate's. Refuses anything else.
    """

    name: str
    source: str
    licence: str
    program_sha256: str
    dialect: Dialect
    stage: Stage
    program_status: Status
    program_refusal: ArrisRefusal | None
    candidate_sha256: str | None
    target_sha256: str | None
    step_sha256: str | None
    score: Score
    versions: Versions

    @model_validator(mode="after")
    def _agree(self) -> Self:
        for sha in (
            self.program_sha256,
            self.candidate_sha256,
            self.target_sha256,
            self.step_sha256,
        ):
            if sha is not None and not _is_sha256(sha):
                raise ValueError("a digest is a hex SHA-256")
        if (self.program_refusal is not None) != (self.program_status is Status.ARRIS_REFUSAL):
            raise ValueError("program_refusal is set exactly when the program ended arris_refusal")
        status = self.score.status
        match self.stage:
            case Stage.NONE:
                if status is not Status.OK or self.program_status is not Status.OK:
                    raise ValueError("stage none means an ok program and an ok score")
            case Stage.PROGRAM:
                if self.program_status is Status.OK or status is not self.program_status:
                    raise ValueError("stage program means the score has the program's failure")
            case Stage.TARGET | Stage.SCORING:
                if self.program_status is not Status.OK or status not in _PAIR_FAILURES:
                    raise ValueError(
                        f"stage {self.stage.value} means an ok program and a "
                        "runtime, timeout or crash score"
                    )
        if self.stage in (Stage.NONE, Stage.SCORING) and (
            self.candidate_sha256 is None or self.target_sha256 is None
        ):
            raise ValueError(f"stage {self.stage.value} has both body digests")
        if self.stage is Stage.TARGET and self.candidate_sha256 is None:
            raise ValueError("stage target has the candidate's body digest")
        return self


class TimedOut(_Frozen):
    """A row that timed out, and the stage it did at, named in the table."""

    name: str
    stage: Stage


def _count(keys: list[str], names: list[str]) -> dict[str, int]:
    """`keys` counted under every name of `names`, zeros included, in that order."""
    return {name: keys.count(name) for name in names}


def _hex(value: float | None) -> str:
    return "none" if value is None else value.hex()


def _digest(rows: tuple[RescoreRow, ...], derived: dict[str, Any]) -> str:
    """The SHA-256 of the rows' identities and the aggregates, floats in hex.

    Per row: name, program status, stage, body digests, `step_sha256` and
    `Score.digest()`; then the counts and means. Messages are left out, since
    a timeout's may carry a duration.
    """
    lines = [
        json.dumps(
            [
                row.name,
                row.program_status.value,
                row.stage.value,
                row.candidate_sha256,
                row.target_sha256,
                row.step_sha256,
                row.score.digest(),
            ]
        )
        for row in rows
    ]
    lines.append(
        json.dumps(
            [
                derived["programs"],
                derived["statuses"],
                derived["stages"],
                derived["iou_routes"],
                _hex(derived["invalidity_rate"]),
                _hex(derived["mean_reward"]),
                derived["valid"],
                _hex(derived["mean_reward_valid"]),
            ]
        )
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _derive(rows: tuple[RescoreRow, ...]) -> dict[str, Any]:
    """Every aggregate of `rows`, each over all of them, and the digest."""
    scores = [row.score for row in rows]
    valid = [s.reward for s in scores if s.status is Status.OK]
    derived: dict[str, Any] = {
        "programs": len(rows),
        "statuses": _count([r.score.status.value for r in rows], [s.value for s in Status]),
        "stages": _count([r.stage.value for r in rows], [s.value for s in Stage]),
        "iou_routes": _count(
            [s.iou_route.value for s in scores if s.iou_route is not None],
            [r.value for r in IouRoute],
        ),
        "invalidity_rate": invalidity_rate(scores),
        "mean_reward": math.fsum(s.reward for s in scores) / len(rows),
        "valid": len(valid),
        "mean_reward_valid": math.fsum(valid) / len(valid) if valid else None,
        "timed_out": tuple(
            TimedOut(name=r.name, stage=r.stage) for r in rows if r.score.status is Status.TIMEOUT
        ),
    }
    derived["digest"] = _digest(rows, derived)
    return derived


class RescoreTable(_Frozen):
    """The re-scored table: `rows` sorted by name, and aggregates over all of them.

    `statuses` counts every `Status` of the rows' scores, `stages` every
    `Stage`, `iou_routes` every `IouRoute` of the scores that have one, all
    with zeros. `invalidity_rate` and `mean_reward` are over all `programs`,
    the failures included; `mean_reward_valid` is the mean over the `valid`
    rows alone, a survivors' figure that is only ever shown beside
    `mean_reward` and labelled so (None with no valid row). `timed_out` names
    each row whose score ended `timeout` and the stage. `digest` is the
    table's identity: the same rows in any order give it, and no wall-clock
    value reaches it.

    Build one with `RescoreTable.of`. Guarantees, enforced on construction:
    at least one row, names unique and sorted, and every aggregate and the
    digest equal to what the rows give; a table that disagrees with its
    rows is refused.

    >>> RescoreTable.of([])
    Traceback (most recent call last):
    ...
    ValueError: a table has at least one row
    """

    rows: tuple[RescoreRow, ...]
    programs: int
    statuses: dict[str, int]
    stages: dict[str, int]
    iou_routes: dict[str, int]
    invalidity_rate: float
    mean_reward: float
    valid: int
    mean_reward_valid: float | None
    timed_out: tuple[TimedOut, ...]
    digest: str

    @classmethod
    def of(cls, rows: list[RescoreRow] | tuple[RescoreRow, ...]) -> RescoreTable:
        """The table of `rows` in any order: sorted by name, aggregates computed.

        Raises `ValueError` for no rows or a name given twice.
        """
        if not rows:
            raise ValueError("a table has at least one row")
        ordered = tuple(sorted(rows, key=lambda r: r.name))
        return cls(rows=ordered, **_derive(ordered))

    @model_validator(mode="after")
    def _agree_with_rows(self) -> Self:
        if not self.rows:
            raise ValueError("a table has at least one row")
        names = [r.name for r in self.rows]
        if names != sorted(set(names)):
            raise ValueError("rows are sorted by name, each name once")
        derived = _derive(self.rows)
        for key, want in derived.items():
            if getattr(self, key) != want:
                raise ValueError(f"{key} disagrees with the rows")
        return self

    def to_json(self) -> str:
        """The table as canonical JSON, digest included: `from_json` returns an equal table."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    @classmethod
    def from_json(cls, text: str) -> Self:
        """Read a table written by `to_json`; refuses one whose digest or counts disagree."""
        return cls.model_validate(json.loads(text))

    def to_markdown(self) -> str:
        """The table as Markdown: the counts, the means (each with its denominator), the rows.

        Every string a program, a kernel or a corpus wrote (a name, a source,
        a licence, a version) is one code span holding its JSON string
        literal, so nothing in it can break the document. `to_json` holds the
        same strings unchanged.
        """

        def counts(name: str, values: dict[str, int]) -> str:
            return f"{name}: " + ", ".join(f"{key} {n}" for key, n in values.items())

        valid = "none" if self.mean_reward_valid is None else f"{self.mean_reward_valid:.6f}"
        reward_versions = sorted({r.score.reward_version for r in self.rows})
        versions = sorted({(r.versions.arris, r.versions.numpy) for r in self.rows})
        lines = [
            "# re-scored table",
            "",
            f"Digest `{self.digest}`.",
            "",
            f"Over {self.programs} programs (every failure counted):",
            "",
            f"- {counts('statuses', self.statuses)}",
            f"- {counts('stages', self.stages)}",
            f"- {counts('IoU routes', self.iou_routes)}",
            f"- invalidity rate {self.invalidity_rate:.6f}",
            f"- mean reward over all {self.programs} programs: {self.mean_reward:.6f}",
            f"- mean reward over the {self.valid} valid programs only "
            f"(survivors, not comparable): {valid}",
            "- timed out: "
            + (", ".join(f"{_code(t.name)} at {t.stage.value}" for t in self.timed_out) or "none"),
            "",
            "Sources: "
            + ", ".join(
                _code(f"{s} ({lic})")
                for s, lic in sorted({(r.source, r.licence) for r in self.rows})
            )
            + ".",
            "arris and numpy: "
            + ", ".join(f"{_code(a)} / {_code(n)}" for a, n in versions)
            + f"; reward version {_code(str(reward_versions))}.",
            "",
            "| name | stage | status | reward | IoU route | IoU | surface | measures | topology |",
            "|---|---|---|---|---|---|---|---|---|",
        ]

        def term(value: float | None) -> str:
            return "" if value is None else f"{value:.4f}"

        for r in self.rows:
            sc = r.score
            route = "" if sc.iou_route is None else sc.iou_route.value
            lines.append(
                f"| {_code(r.name)} | {r.stage.value} | {sc.status.value} | {sc.reward:.4f} | "
                f"{route} | {term(sc.iou)} | {term(sc.surface)} | {term(sc.measures)} | "
                f"{term(sc.topology)} |"
            )
        return "\n".join(lines) + "\n"
