#!/usr/bin/env python3
"""Digest Claude Code and Codex transcripts for /retro."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path

SHOW = 600
REPORT_START = "The report follows:"
SESSION_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE)
BASH_READ = re.compile(
    r"""(?:^|[\s;&|("`])(?:cat|head|tail|sed\s+-n\s+\S+)(?:\s+-\S+)*\s+([\w./~-]+\.\w+)"""
)
CODEX_ERROR = re.compile(
    r"""(?:["']exit_code["']\s*:\s*|(?:Process exited with code|Exit code:)\s*)[1-9]\d*\b"""
    r"|^Error:|^Script failed",
    re.IGNORECASE,
)
FRAMES = (
    "<system-reminder>",
    "<local-command",
    "<command-",
    "<task-notification",
    "Base directory",
    "# AGENTS.md instructions",
    "<environment_context>",
    "<skill>",
)


def _object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _transcript(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                entry = _object(json.loads(line))
            except json.JSONDecodeError:
                continue
            if entry:
                yield line, entry


def _blocks(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [block for block in content if isinstance(block, dict)]
    return []


def _codex_blocks(payload: dict[str, object]) -> list[dict[str, object]]:
    kind = payload.get("type")
    if kind == "message" and payload.get("role") == "user":
        return [
            {"type": "text", "text": block.get("text")}
            for block in _blocks(payload.get("content"))
            if block.get("type") in ("text", "input_text")
        ]
    if kind == "agent_message":
        hand_backs: list[dict[str, object]] = []
        for block in _blocks(payload.get("content")):
            text = str(block.get("text", ""))
            report = text.partition("\nPayload:\n")[2].strip()
            if text.startswith("Message Type: FINAL_ANSWER\n") and report:
                hand_backs.append({"type": "hand_back", "text": report})
        return hand_backs
    if kind in ("custom_tool_call", "function_call"):
        tool_input = payload.get("input")
        if kind == "function_call":
            arguments = str(payload.get("arguments", ""))
            try:
                tool_input = json.loads(arguments)
            except json.JSONDecodeError:
                tool_input = arguments
        if isinstance(tool_input, str):
            tool_input = {"command": tool_input}
        return [
            {
                "type": "tool_use",
                "name": payload.get("name"),
                "id": payload.get("call_id"),
                "input": tool_input,
            }
        ]
    if kind in ("custom_tool_call_output", "function_call_output"):
        output = str(payload.get("output", ""))
        if error := CODEX_ERROR.search(output):
            return [
                {
                    "type": "tool_result",
                    "is_error": True,
                    "tool_use_id": payload.get("call_id"),
                    "content": output[error.start() :],
                }
            ]
    return []


def _relative(path: str, root: str) -> str:
    return path.removeprefix(root + "/") if root else path


def digest(path: Path) -> None:
    """Print user messages, tool counts, failures, repeated reads and hand-backs."""
    print(f"===== {path}")
    uses: dict[str, str] = {}
    counts: Counter[str] = Counter()
    reads: Counter[str] = Counter()
    failures: list[str] = []
    root = ""
    for _, entry in _transcript(path):
        kind = entry.get("type")
        if kind == "session_meta":
            root = str(_object(entry.get("payload")).get("cwd", ""))
            continue
        if kind == "response_item":
            blocks = _codex_blocks(_object(entry.get("payload")))
        elif kind in ("user", "assistant"):
            root = root or str(entry.get("cwd", ""))
            blocks = _blocks(_object(entry.get("message")).get("content"))
        else:
            continue
        when = str(entry.get("timestamp", ""))[11:19]
        for block in blocks:
            block_kind = block.get("type")
            if block_kind == "hand_back":
                print(f"-- {when} HAND-BACK: {str(block.get('text', ''))[:SHOW]!r}")
            elif block_kind == "text" and kind != "assistant":
                text = str(block.get("text", ""))
                if text.startswith(FRAMES):
                    continue
                text = text.partition("\n<skill>")[0].strip()
                label = "human"
                if "Subagent hand-back" in text:
                    label = "HAND-BACK"
                    text = text.partition(REPORT_START)[2].strip() or text
                if text:
                    print(f"-- {when} {label}: {text[:SHOW]!r}")
            elif block_kind == "tool_use":
                name = str(block.get("name"))
                call_id = str(block.get("id"))
                if call_id in uses:
                    continue
                uses[call_id] = name
                counts[name] += 1
                tool_input = _object(block.get("input"))
                if name == "Read" and "file_path" in tool_input:
                    reads[_relative(str(tool_input["file_path"]), root)] += 1
                command = tool_input.get("command", tool_input.get("cmd"))
                if isinstance(command, str):
                    for target in BASH_READ.findall(command):
                        reads[_relative(target, root)] += 1
            elif block_kind == "tool_result" and block.get("is_error"):
                name = uses.get(str(block.get("tool_use_id")), "unknown tool")
                failures.append(f"{name}: {str(block.get('content'))[:SHOW]!r}")
    print("tools:", dict(counts))
    print("read more than once:", {p: n for p, n in sorted(reads.items()) if n > 1})
    for failure in failures:
        print("FAILED", failure)


def _matches(path: Path, query: str, checkout: Path, *, codex: bool) -> bool:
    query_is_id = SESSION_ID.fullmatch(query) is not None
    if query_is_id and not path.stem.lower().endswith(query.lower()):
        return False

    same_checkout = not codex
    for raw, entry in _transcript(path):
        kind = entry.get("type")
        if codex and kind == "session_meta":
            cwd = _object(entry.get("payload")).get("cwd")
            same_checkout = isinstance(cwd, str) and Path(cwd).resolve() == checkout
            if not same_checkout:
                return False
        if not same_checkout:
            continue
        if query_is_id:
            return True
        if query not in raw:
            continue
        if kind in ("user", "assistant"):
            return True
        if kind == "response_item":
            payload = _object(entry.get("payload"))
            if payload.get("type") == "message":
                if payload.get("role") in ("assistant", "user"):
                    return True
            elif payload.get("type") in (
                "agent_message",
                "custom_tool_call",
                "custom_tool_call_output",
                "function_call",
                "function_call_output",
            ):
                return True
    return False


def _subagents(path: Path) -> list[Path]:
    return sorted(path.with_suffix("").glob("subagents/*.jsonl"))


def _find(checkout: Path, query: str) -> list[Path]:
    home = Path.home()
    claude_project = str(checkout).replace("/", "-")
    claude = home.glob(f".claude*/projects/{claude_project}/*.jsonl")
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex").expanduser()
    codex = (
        path
        for folder in ("sessions", "archived_sessions")
        for path in (codex_home / folder).rglob("rollout-*.jsonl")
    )
    matched = {
        path
        for path in claude
        if any(_matches(p, query, checkout, codex=False) for p in (path, *_subagents(path)))
    }
    matched.update(path for path in codex if _matches(path, query, checkout, codex=True))
    return sorted(matched)


def main(argv: Sequence[str] | None = None) -> int:
    """Digest explicit JSONL paths or find sessions for a checkout and plan or ID."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcripts", type=Path, nargs="*", metavar="TRANSCRIPT.jsonl")
    parser.add_argument("--find", metavar="PLAN_SLUG_OR_SESSION_ID")
    parser.add_argument(
        "--checkout", type=Path, default=Path.cwd(), help="defaults to the current directory"
    )
    args = parser.parse_args(argv)
    paths: list[Path] = args.transcripts
    if args.find:
        if paths:
            parser.error("--find and transcript paths are mutually exclusive")
        paths = _find(args.checkout.resolve(), args.find)
        if not paths:
            print(
                f"No transcripts matched {args.find!r} in {args.checkout.resolve()}",
                file=sys.stderr,
            )
            return 1
    elif not paths:
        parser.error("provide transcript paths or --find")

    for path in paths:
        digest(path)
        for agent in _subagents(path):
            digest(agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
