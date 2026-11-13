#!/usr/bin/env python3
"""Digest Claude Code transcripts for `/retro`.

Usage: tools/session-digest.py TRANSCRIPT.jsonl...
Per transcript prints the human's messages (with time), tool-call counts,
failed tool calls, files read more than once (by `Read` or by `cat`, `head`,
`tail` or `sed -n` in Bash) and subagent hand-backs (the report, without the
harness's frame). A session's subagents (`<session>/subagents/*.jsonl`) follow
it. Only `user` and `assistant` entries count: a transcript's `api-request-blob`
entries repeat their calls.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

SHOW = 600  # characters of a message, error or report that are printed
# A hand-back's report starts after this line of the harness's frame.
REPORT_START = "The report follows:"
# A Bash command reading a file: `cat`, `head`, `tail` or `sed -n RANGE`, its flags, a path.
BASH_READ = re.compile(
    r"(?:^|[\s;&|(])(?:cat|head|tail|sed\s+-n\s+\S+)(?:\s+-\S+)*\s+([\w./~-]+\.\w+)"
)


def blocks(entry: dict[str, object]) -> list[dict[str, object]]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def relative(path: str, root: str) -> str:
    """`path` without the `root/` it starts with, so one file read two ways counts once."""
    return path.removeprefix(root + "/") if root else path


def digest(path: Path) -> None:
    print(f"===== {path.name}")
    uses: dict[str, dict[str, object]] = {}
    counts: Counter[str] = Counter()
    reads: Counter[str] = Counter()
    failures: list[str] = []
    root = ""  # the session's first working directory; read paths are shown relative to it
    for raw in path.read_text().splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("type") not in ("user", "assistant"):
            continue
        root = root or str(entry.get("cwd", ""))
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
                label = "human"
                if "Subagent hand-back" in text:
                    label = "HAND-BACK"
                    text = text.partition(REPORT_START)[2].strip() or text
                print(f"-- {when} {label}: {text[:SHOW]!r}")
            elif kind == "tool_use":
                name = str(block.get("name"))
                if str(block.get("id")) in uses:
                    continue
                uses[str(block.get("id"))] = block
                counts[name] += 1
                tool_input = block.get("input")
                if name == "Read" and isinstance(tool_input, dict):
                    reads[relative(str(tool_input.get("file_path")), root)] += 1
                if name == "Bash" and isinstance(tool_input, dict):
                    for target in BASH_READ.findall(str(tool_input.get("command", ""))):
                        reads[relative(target, root)] += 1
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
        for agent in sorted(Path(name).with_suffix("").glob("subagents/*.jsonl")):
            digest(agent)


if __name__ == "__main__":
    main()
