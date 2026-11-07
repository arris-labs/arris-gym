#!/usr/bin/env python3
"""Digest Claude Code transcripts for `/retro`.

Usage: tools/session-digest.py TRANSCRIPT.jsonl...
Per transcript prints the human's messages (with time), tool-call counts,
failed tool calls, files read more than once and subagent hand-backs.
"""

import json
import sys
from collections import Counter
from pathlib import Path

SHOW = 600  # characters of a message, error or report that are printed


def blocks(entry: dict[str, object]) -> list[dict[str, object]]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def digest(path: Path) -> None:
    print(f"===== {path.name}")
    uses: dict[str, dict[str, object]] = {}
    counts: Counter[str] = Counter()
    reads: Counter[str] = Counter()
    failures: list[str] = []
    for raw in path.read_text().splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        when = str(entry.get("timestamp", ""))[11:19]
        for block in blocks(entry):
            kind = block.get("type")
            if kind == "text" and entry.get("type") == "user":
                text = str(block.get("text", ""))
                if text.startswith(
                    (
                        "<system-reminder>",
                        "<local-command",
                        "<command-",
                        "<task-notification",
                        "Base directory",
                    )
                ):
                    continue
                label = "HAND-BACK" if "Subagent hand-back" in text else "human"
                print(f"-- {when} {label}: {text[:SHOW]!r}")
            elif kind == "tool_use":
                name = str(block.get("name"))
                uses[str(block.get("id"))] = block
                counts[name] += 1
                tool_input = block.get("input")
                if name == "Read" and isinstance(tool_input, dict):
                    reads[str(tool_input.get("file_path"))] += 1
            elif kind == "tool_result" and block.get("is_error"):
                use = uses.get(str(block.get("tool_use_id")), {})
                failures.append(f"{use.get('name')}: {str(block.get('content'))[:SHOW]!r}")
    print("tools:", dict(counts))
    print("read more than once:", {p: n for p, n in sorted(reads.items()) if n > 1})
    for failure in failures:
        print("FAILED", failure)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for name in sys.argv[1:]:
        digest(Path(name))


if __name__ == "__main__":
    main()
