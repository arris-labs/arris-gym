"""The frozen inputs to the offline Vision2Code comparison (ADR-0032)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from arris_gym.census import benchcad
from arris_gym.sandbox._target import step_sha256

_UPSTREAM_COMMIT = "77fd16a80a4e5fc39964ee23b6cc3225beefac8f"
_ORACLE_LOCK = Path(__file__).resolve().parents[1] / "oracle/uv.lock"
_IOU_DECIMALS = 4  # The pinned regrader's per-record precision (ADR-0032).
_MANIFEST_VERSION = 1

_Outcome = Literal["missing", "blank", "export_error", "timeout", "crash", "scored"]
_PredictionOutcome = Literal[
    "missing", "blank", "generation_failed", "extraction_failed", "program"
]

_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_RecordID = Annotated[str, Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")]
_Nonempty = Annotated[str, Field(min_length=1)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_sha(text: str | None) -> str | None:
    return None if text is None else _sha(text.encode("utf-8"))


class UpstreamGrade(_Frozen):
    """The observed outcome and voxel IoU at the pinned regrader's precision.

    Every outcome other than `scored` has IoU zero. A timeout or crash
    records whether it happened during export or scoring.
    """

    outcome: _Outcome
    iou: float = Field(ge=0, le=1)
    message: str = ""
    stage: Literal["export", "scoring"] | None = None

    @model_validator(mode="after")
    def _check_grade(self) -> Self:
        if self.iou != round(self.iou, _IOU_DECIMALS):
            raise ValueError("upstream IoU must have the regrader's precision")
        if self.outcome != "scored" and self.iou != 0.0:
            raise ValueError("an upstream failure must have zero IoU")
        if (self.stage is not None) != (self.outcome in ("timeout", "crash")):
            raise ValueError(
                "an upstream stage is required for a timeout or crash and omitted otherwise"
            )
        return self


class _Record(_Frozen):
    record_id: _RecordID


class _Task(_Record):
    stem: _Nonempty
    family: _Nonempty
    source: _Nonempty
    licence: _Nonempty
    reference_sha256: _Sha256
    target_sha256: _Sha256
    step_sha256: _Sha256 | None
    render_sha256: _Sha256

    @model_validator(mode="after")
    def _check_stem(self) -> Self:
        if self.record_id != self.stem:
            raise ValueError("the official record ID must match the stem")
        return self


class _Pins(_Frozen):
    code_gen_revision: str
    upstream_commit: str
    oracle_lock_sha256: _Sha256

    @model_validator(mode="after")
    def _check_pins(self) -> Self:
        if (self.code_gen_revision, self.upstream_commit) != (benchcad.REVISION, _UPSTREAM_COMMIT):
            raise ValueError("the BenchCAD corpus or upstream commit differs from the pilot pin")
        if self.oracle_lock_sha256 != _sha(_ORACLE_LOCK.read_bytes()):
            raise ValueError("the upstream environment differs from the pilot lock")
        return self


class _Manifest(_Frozen):
    version: int = Field(ge=_MANIFEST_VERSION, le=_MANIFEST_VERSION)
    pins: _Pins
    tasks: tuple[_Task, ...] = Field(min_length=1)


class _Prediction(_Record):
    model: _Nonempty
    model_revision: _Nonempty
    licence: _Nonempty
    prompt: str
    prompt_sha256: _Sha256
    render_sha256: _Sha256
    decoding: dict[str, JsonValue]
    raw_response: str | None
    raw_response_sha256: _Sha256 | None
    program: str | None
    program_sha256: _Sha256 | None
    failure: Literal["generation_failed", "extraction_failed"] | None = None

    @model_validator(mode="after")
    def _check_capture(self) -> Self:
        if (
            self.prompt_sha256 != _text_sha(self.prompt)
            or self.raw_response_sha256 != _text_sha(self.raw_response)
            or self.program_sha256 != _text_sha(self.program)
        ):
            raise ValueError(f"prediction text hash differs at {self.record_id}")
        required = {
            None: (True, True),
            "generation_failed": (False, False),
            "extraction_failed": (True, False),
        }
        if (self.raw_response is not None, self.program is not None) != required[self.failure]:
            raise ValueError(f"prediction failure disagrees with captured text at {self.record_id}")
        return self

    def _outcome(self) -> _PredictionOutcome:
        if self.failure is not None:
            return self.failure
        return "program" if self.program and self.program.strip() else "blank"


class _Grade(_Record):
    target_sha256: _Sha256
    program_sha256: _Sha256 | None
    grade: UpstreamGrade


def _read_rows[T: _Record](path: Path, model: type[T]) -> list[T]:
    return [model.model_validate_json(line) for line in path.read_bytes().splitlines()]


def _by_id[T: _Record](records: list[T] | tuple[T, ...], label: str) -> dict[str, T]:
    rows: dict[str, T] = {}
    for row in records:
        if row.record_id in rows:
            raise ValueError(f"duplicate {label} ID {row.record_id}")
        rows[row.record_id] = row
    return rows


class _Input(_Frozen):
    task: _Task
    target: str
    prediction: _Prediction | None
    upstream: UpstreamGrade

    def _prediction_outcome(self) -> _PredictionOutcome:
        return "missing" if self.prediction is None else self.prediction._outcome()

    def _program(self) -> str:
        if self.prediction is None or self._prediction_outcome() != "program":
            return ""
        assert self.prediction.program is not None
        return self.prediction.program


def _load(bundle: Path) -> tuple[_Pins, dict[str, _Input]]:
    manifest = _Manifest.model_validate_json((bundle / "manifest.json").read_bytes())
    tasks = _by_id(manifest.tasks, "manifest")
    predictions = _by_id(_read_rows(bundle / "predictions.jsonl", _Prediction), "prediction")
    upstream = _by_id(_read_rows(bundle / "upstream.jsonl", _Grade), "upstream")
    if foreign := sorted(predictions.keys() - tasks.keys()):
        raise ValueError(f"foreign prediction IDs: {', '.join(foreign)}")
    if tasks.keys() != upstream.keys():
        missing = sorted(tasks.keys() - upstream.keys())
        foreign = sorted(upstream.keys() - tasks.keys())
        raise ValueError(f"upstream IDs differ from manifest: missing {missing}, foreign {foreign}")

    inputs: dict[str, _Input] = {}
    for record_id, task in sorted(tasks.items()):
        prediction = predictions.get(record_id)
        row = upstream[record_id]
        data = (bundle / "targets" / f"{record_id}.step").read_bytes()
        if task.target_sha256 != _sha(data) or row.target_sha256 != task.target_sha256:
            raise ValueError(f"target file hash differs at {record_id}")
        target = data.decode("utf-8")
        if task.step_sha256 != step_sha256(target):
            raise ValueError(f"STEP data-section hash differs at {record_id}")
        if prediction is not None and prediction.render_sha256 != task.render_sha256:
            raise ValueError(f"prediction render hash differs at {record_id}")
        if row.program_sha256 != (None if prediction is None else prediction.program_sha256):
            raise ValueError(f"upstream program hash differs at {record_id}")
        observed = _Input(task=task, target=target, prediction=prediction, upstream=row.grade)
        match observed._prediction_outcome():
            case "program":
                allowed = row.grade.outcome not in ("blank", "missing")
            case "blank":
                allowed = row.grade.outcome == "blank"
            case "missing" | "generation_failed" | "extraction_failed":
                allowed = row.grade.outcome == "missing"
        if not allowed:
            raise ValueError(f"upstream outcome disagrees with prediction at {record_id}")
        inputs[record_id] = observed
    return manifest.pins, inputs


def _json(payload: dict[str, JsonValue]) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
