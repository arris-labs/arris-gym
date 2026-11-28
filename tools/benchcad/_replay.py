"""Compare frozen BenchCAD grades with offline Gym re-scoring (ADR-0032)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import get_args

from pydantic import JsonValue

from arris_gym._markdown import code_span
from arris_gym.rescore import RescoreEntry, RescoreTable, rescore
from arris_gym.reward._scoring import DEFAULT_SCORE_TIMEOUT
from arris_gym.sandbox import Dialect, Status
from benchcad._bundle import _Input, _json, _load, _Outcome, _PredictionOutcome, _sha

_NORMALIZATION = (
    "BenchCAD centers each tessellated body at its own bounding-box center "
    "and scales its own longest axis to 1 before voxelization. "
    "Gym geometry IoU uses the bodies in their original coordinates."
)


def _mean(values: Sequence[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _entry(data: _Input) -> RescoreEntry:
    task = data.task
    return RescoreEntry(
        name=task.record_id,
        source=task.source,
        licence=task.licence,
        dialect=Dialect.CQ,
        program=data._program(),
        step=data.target,
    )


def _comparison(inputs: dict[str, _Input], table: RescoreTable) -> dict[str, JsonValue]:
    rows: list[JsonValue] = []
    program_statuses: Counter[str] = Counter()
    upstream_outcomes: Counter[str] = Counter()
    prediction_outcomes: Counter[str] = Counter()
    upstream_ious: list[float] = []
    paired_upstream_ious: list[float] = []
    paired_gym_ious: list[float] = []
    gym_ious: list[float] = []
    field_ious: list[float] = []
    chamfers: list[float] = []
    upstream_timeouts: list[JsonValue] = []
    upstream_scored_zero = 0
    for gym in table.rows:
        data = inputs[gym.name]
        upstream = data.upstream
        prediction = data.prediction
        prediction_outcome = data._prediction_outcome()
        program_statuses[gym.program_status.value] += 1
        upstream_outcomes[upstream.outcome] += 1
        prediction_outcomes[prediction_outcome] += 1
        upstream_ious.append(upstream.iou)
        if upstream.outcome == "timeout":
            upstream_timeouts.append({"record_id": gym.name, "stage": upstream.stage})
        if upstream.outcome == "scored" and upstream.iou == 0:
            upstream_scored_zero += 1

        iou, field = gym.score.iou, gym.score.field
        if iou is not None and field is not None:
            gym_ious.append(iou)
            field_ious.append(field.voxel_iou_64)
            chamfers.append(field.chamfer_x1000)
            if upstream.outcome == "scored":
                paired_gym_ious.append(iou)
                paired_upstream_ious.append(upstream.iou)

        rows.append(
            {
                "task": data.task.model_dump(mode="json"),
                "prediction_outcome": prediction_outcome,
                "prediction": None
                if prediction is None
                else prediction.model_dump(
                    mode="json", exclude={"prompt", "raw_response", "program"}
                ),
                "upstream": upstream.model_dump(mode="json", exclude={"message"}),
                "gym": gym.model_dump(
                    mode="json", exclude={"score": {"message"}, "program_refusal": {"message"}}
                ),
            }
        )
    return {
        "normalization": _NORMALIZATION,
        "rows": rows,
        "gym_digest": table.digest,
        "aggregates": {
            "records": table.programs,
            "prediction_outcomes": {
                k: prediction_outcomes[k] for k in get_args(_PredictionOutcome)
            },
            "upstream_outcomes": {k: upstream_outcomes[k] for k in get_args(_Outcome)},
            "upstream_zero_iou": upstream_ious.count(0.0),
            "upstream_scored_zero_iou": upstream_scored_zero,
            "upstream_mean_voxel_iou_all": _mean(upstream_ious),
            "gym_program_statuses": {s.value: program_statuses[s.value] for s in Status},
            "gym_score_statuses": {**table.statuses},
            "gym_stages": {**table.stages},
            "gym_invalid": table.programs - table.valid,
            "gym_invalidity_rate": table.invalidity_rate,
            "gym_mean_reward_all": table.mean_reward,
            "gym_iou_routes": {**table.iou_routes},
            "gym_survivors": {
                "records": table.valid,
                "mean_reward": table.mean_reward_valid,
                "mean_geometry_iou": _mean(gym_ious),
                "mean_voxel_iou_64": _mean(field_ious),
                "mean_chamfer_x1000": _mean(chamfers),
            },
            "paired_scored": {
                "records": len(paired_gym_ious),
                "mean_upstream_voxel_iou": _mean(paired_upstream_ious),
                "mean_gym_geometry_iou": _mean(paired_gym_ious),
            },
            "gym_timeouts": [t.model_dump(mode="json") for t in table.timed_out],
            "upstream_timeouts": upstream_timeouts,
        },
    }


def _term(value: float | None) -> str:
    return "—" if value is None else f"{value:.6f}"


def _markdown(inputs: dict[str, _Input], table: RescoreTable, report: dict[str, JsonValue]) -> str:
    aggregates = report["aggregates"]
    assert isinstance(aggregates, dict)
    lines = [
        "# BenchCAD Vision2Code comparison",
        "",
        f"Comparison digest `{report['digest']}`. Gym digest `{table.digest}`.",
        "",
        _NORMALIZATION,
        "",
        f"All-task counts and means cover {table.programs} records.",
        "An upstream scored zero can leave the cause unknown.",
        "An upstream timeout can occur during export or scoring.",
        "",
        "| Measure | Value |",
        "|---|---|",
    ]
    for key, value in aggregates.items():
        label = key.replace("_", " ")
        if key.endswith("timeouts"):
            continue
        if isinstance(value, dict):
            for term, count in value.items():
                rendered = _term(count) if isinstance(count, float) or count is None else count
                lines.append(f"| {label} · {term.replace('_', ' ')} | {rendered} |")
        else:
            rendered = _term(value) if isinstance(value, float) or value is None else value
            lines.append(f"| {label} | {rendered} |")
    timed_out = [f"{code_span(t.name)} at Gym {t.stage.value}" for t in table.timed_out] + [
        f"{code_span(name)} at upstream {data.upstream.stage}"
        for name, data in inputs.items()
        if data.upstream.outcome == "timeout"
    ]
    lines.extend(
        [
            "",
            "Timed out — " + (", ".join(timed_out) or "none") + ".",
            "",
            "| Official record ID | Prediction | Upstream outcome | Upstream voxel IoU | "
            "Gym stage | Gym status | Gym route | Gym geometry IoU | Gym voxel IoU | "
            "Gym Chamfer x1000 | Gym reward |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for gym in table.rows:
        data = inputs[gym.name]
        sc = gym.score
        field = sc.field
        route = "—" if sc.iou_route is None else sc.iou_route.value
        voxel = None if field is None else field.voxel_iou_64
        chamfer = None if field is None else field.chamfer_x1000
        lines.append(
            f"| {code_span(gym.name)} | {data._prediction_outcome()} | "
            f"{data.upstream.outcome} | {data.upstream.iou:.4f} | {gym.stage.value} | "
            f"{sc.status.value} | {route} | {_term(sc.iou)} | {_term(voxel)} | "
            f"{_term(chamfer)} | {_term(sc.reward)} |"
        )
    return "\n".join(lines) + "\n"


def _replay(
    bundle: Path,
    out: Path,
    *,
    record_id: str | None = None,
    workers: int | None = None,
    score_timeout: float = DEFAULT_SCORE_TIMEOUT,
) -> None:
    pins, inputs = _load(bundle)
    if record_id is not None:
        if record_id not in inputs:
            raise ValueError(f"unknown manifest ID {record_id}")
        inputs = {record_id: inputs[record_id]}
    table = rescore(
        [_entry(data) for data in inputs.values()],
        workers=workers,
        score_timeout=score_timeout,
    )
    report = _comparison(inputs, table)
    report["version"] = 1
    report["pins"] = pins.model_dump(mode="json")
    report["digest"] = _sha(_json(report).encode("utf-8"))

    out.mkdir(parents=True, exist_ok=False)
    (out / "rescore.json").write_text(table.to_json() + "\n", encoding="utf-8")
    (out / "rescore.md").write_text(table.to_markdown(), encoding="utf-8")
    (out / "comparison.json").write_text(_json(report) + "\n", encoding="utf-8")
    (out / "comparison.md").write_text(_markdown(inputs, table, report), encoding="utf-8")
    print(f"{table.programs} records, comparison digest {report['digest']}")
