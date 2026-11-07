"""The frame: what a program worker tells the caller, as one JSON document.

Written by `sandbox/_program.py` inside the worker, parsed by
`sandbox/_run.py` in the caller. The caller never trusts one (a program can
reach the result pipe and write its own); parsing is where it is refused.
Private.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from arris_gym.sandbox.outcome import ArrisRefusal, Measures, Status


class Frame(BaseModel):
    """The worker's account of how a program ended, before the caller adds
    the program's digest, dialect, versions and the seconds it took.

    `body` travels as base64 in JSON: it is the worker's `write_body` bytes.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64"
    )

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: bytes | None
    measures: Measures | None
    violations: tuple[str, ...]
