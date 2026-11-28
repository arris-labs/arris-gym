"""Capture predictions without running or grading model-written programs."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from benchcad._bundle import _by_id, _Manifest, _Prediction, _sha, _text_sha
from benchcad._qwen import _DECODING, _LICENCE, _MODEL, _REVISION


def _capture_predictions(
    bundle: Path,
    out: Path,
    *,
    prompt: Callable[[bytes, bytes], tuple[str, str]],
    generate: Callable[[str, str, bytes], str | None],
    extract: Callable[[str], bytes],
    record_ids: Sequence[str] | None = None,
) -> None:
    """Write one validated row per selected ID. A model failure returns None."""
    manifest = _Manifest.model_validate_json((bundle / "manifest.json").read_bytes())
    tasks = _by_id(manifest.tasks, "manifest")
    selected = sorted(tasks) if record_ids is None else sorted(record_ids)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("generation requires a nonempty selection of unique IDs")
    if foreign := sorted(set(selected) - tasks.keys()):
        raise ValueError(f"foreign prediction IDs: {', '.join(foreign)}")

    first = selected[0]
    first_target = b""
    renders = {}
    for record_id, task in tasks.items():
        render = (bundle / "renders" / f"{record_id}.png").read_bytes()
        if _sha(render) != task.render_sha256:
            raise ValueError(f"render file hash differs at {record_id}")
        renders[record_id] = render
        target = (bundle / "targets" / f"{record_id}.step").read_bytes()
        if _sha(target) != task.target_sha256:
            raise ValueError(f"target file hash differs at {record_id}")
        if record_id == first:
            first_target = target
    # The pinned builder's texts are fixed across records. Generation sees
    # exactly these texts and the corresponding opaque PNG bytes.
    system, user = prompt(first_target, renders[first])
    prompt_text = json.dumps({"system": system, "user": user}, ensure_ascii=False, sort_keys=True)

    with out.open("x", encoding="utf-8", newline="\n") as predictions:
        for record_id in selected:
            raw = generate(system, user, renders[record_id])
            program = None
            failure: Literal["generation_failed", "extraction_failed"] | None = None
            if raw is None:
                failure = "generation_failed"
            else:
                try:
                    program = extract(raw).decode("utf-8")
                except (OSError, RuntimeError, UnicodeError):
                    failure = "extraction_failed"
            row = _Prediction(
                record_id=record_id,
                model=_MODEL,
                model_revision=_REVISION,
                licence=_LICENCE,
                prompt=prompt_text,
                prompt_sha256=_sha(prompt_text.encode("utf-8")),
                render_sha256=tasks[record_id].render_sha256,
                decoding=dict(_DECODING),
                raw_response=raw,
                raw_response_sha256=_text_sha(raw),
                program=program,
                program_sha256=_text_sha(program),
                failure=failure,
            )
            predictions.write(row.model_dump_json() + "\n")
            predictions.flush()
