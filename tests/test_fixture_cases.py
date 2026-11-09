"""The fixture loader's per-machine message (`fixture_cases.for_machine`)."""

from __future__ import annotations

import json

import pytest

import fixture_cases

ABORT = fixture_cases.ROOT / "sandbox" / "crash-abort"


def _declared() -> dict[str, object]:
    expected: dict[str, object] = json.loads((ABORT / "expected.json").read_text("utf-8"))
    return expected


def test_a_fixture_without_one_keeps_its_single_expectation() -> None:
    expected: dict[str, object] = {"dialect": "arris", "status": "crash", "message": "m"}
    assert fixture_cases.for_machine(expected, "x", "riscv64") is expected


def test_crash_abort_declares_a_signal_for_each_machine_the_gate_runs_on() -> None:
    declared = _declared()
    assert "message" not in declared
    for machine, signal in (("x86_64", "SIGSEGV"), ("aarch64", "SIGTRAP")):
        got = fixture_cases.for_machine(declared, "crash-abort", machine)
        assert fixture_cases.BY_MACHINE not in got
        assert got["message"] == (
            f"the program worker was killed by {signal}; its stderr ends:\nthe last words\n"
        )


def test_a_machine_with_no_declared_expectation_is_refused() -> None:
    with pytest.raises(ValueError, match="no expected message for machine 'riscv64'"):
        fixture_cases.for_machine(_declared(), "crash-abort", "riscv64")


def test_a_message_beside_one_per_machine_is_refused() -> None:
    both = _declared() | {"message": "m"}
    with pytest.raises(ValueError, match="in place of message"):
        fixture_cases.for_machine(both, "crash-abort", "x86_64")
