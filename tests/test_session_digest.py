"""Both JSONL transcript formats can be found and digested without real sessions."""

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "session-digest.py"
PLAN = "corpus-replay"
CODEX_ID = "01234567-89ab-cdef-0123-456789abcdef"
CLAUDE_ID = "fedcba98-7654-3210-fedc-ba9876543210"


def write_transcript(path: Path, *entries: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
    return path


@pytest.fixture
def transcripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    claude_project = home / ".claude-2" / "projects" / str(checkout).replace("/", "-")
    claude = write_transcript(
        claude_project / f"{CLAUDE_ID}.jsonl",
        {"type": "user", "cwd": str(checkout), "message": {"content": f"/work {PLAN}"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "read",
                        "name": "Read",
                        "input": {"file_path": str(checkout / "plan.md")},
                    },
                    {
                        "type": "tool_use",
                        "id": "bash",
                        "name": "Bash",
                        "input": {"command": "cat plan.md"},
                    },
                ]
            },
        },
        {"type": "api-request-blob", "message": {"content": "ignore repeated request"}},
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "bash",
                        "is_error": True,
                        "content": "read failed",
                    }
                ]
            },
        },
    )
    codex_events: list[dict[str, object]] = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": f"$work {PLAN}"}],
        },
        {
            "type": "function_call",
            "call_id": "cmd",
            "name": "exec_command",
            "arguments": json.dumps({"cmd": "cat plan.md"}),
        },
        {
            "type": "custom_tool_call",
            "call_id": "exec",
            "name": "exec",
            "input": f'text(await tools.exec_command({{cmd:"cat {checkout}/plan.md"}}))',
        },
        {"type": "function_call_output", "call_id": "cmd", "output": "Process exited with code 1"},
        {"type": "custom_tool_call_output", "call_id": "exec", "output": '{"exit_code": 0}'},
        {
            "type": "agent_message",
            "content": [
                {"type": "input_text", "text": "Message Type: FINAL_ANSWER\nPayload:\ncomplete"}
            ],
        },
    ]
    codex = write_transcript(
        home / ".codex" / "archived_sessions" / f"rollout-2026-11-27T12-00-00-{CODEX_ID}.jsonl",
        {"type": "session_meta", "payload": {"id": CODEX_ID, "cwd": str(checkout)}},
        *({"type": "response_item", "payload": event} for event in codex_events),
    )
    write_transcript(
        home / ".codex" / "sessions" / "2026" / "11" / "27" / "rollout-other.jsonl",
        {"type": "session_meta", "payload": {"cwd": str(tmp_path / "other-checkout")}},
        {"type": "response_item", "payload": codex_events[0]},
    )
    return checkout, claude, codex


def test_find_plan_and_parse_both_formats(transcripts: tuple[Path, Path, Path]) -> None:
    checkout, claude, codex = transcripts
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--find", PLAN, "--checkout", str(checkout)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert f"===== {claude}" in result.stdout
    assert f"===== {codex}" in result.stdout
    assert "rollout-other.jsonl" not in result.stdout
    assert f"human: '/work {PLAN}'" in result.stdout
    assert f"human: '$work {PLAN}'" in result.stdout
    assert result.stdout.count("read more than once: {'plan.md': 2}") == 2
    assert "tools: {'Read': 1, 'Bash': 1}" in result.stdout
    assert "tools: {'exec_command': 1, 'exec': 1}" in result.stdout
    assert "FAILED Bash: 'read failed'" in result.stdout
    assert "FAILED exec_command: 'Process exited with code 1'" in result.stdout
    assert "HAND-BACK: 'complete'" in result.stdout


def test_find_session_by_id_and_keep_explicit_paths(transcripts: tuple[Path, Path, Path]) -> None:
    checkout, claude, codex = transcripts
    base = [sys.executable, str(SCRIPT)]
    found = subprocess.run(
        [*base, "--find", CODEX_ID, "--checkout", str(checkout)],
        check=True,
        capture_output=True,
        text=True,
    )
    explicit = subprocess.run([*base, str(codex)], check=True, capture_output=True, text=True)
    assert found.stdout == explicit.stdout
    assert f"===== {codex}" in found.stdout
    assert str(claude) not in found.stdout
