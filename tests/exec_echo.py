"""The script `tests/test_exec.py` execs in an exec job, on the main interpreter.

Usage: `exec_echo.py PAYLOAD_FD RESULT_FD [CHANNEL_FD]`. Reads the text to
its end and writes one JSON report to the result descriptor: the text, its
own pid, and what reading a file beside it and executing another program
raised. With a channel (ADR-0013), it also reports the message it received
on it and answers it reversed.
"""

import json
import os
import socket
import sys
from collections.abc import Callable


def attempt(action: Callable[[], object]) -> list[object]:
    try:
        action()
    except OSError as e:
        return [type(e).__name__, e.errno]
    return ["ok", None]


def read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def main() -> None:
    payload, result = int(sys.argv[1]), int(sys.argv[2])
    chunks = []
    while chunk := os.read(payload, 1 << 16):
        chunks.append(chunk)
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture_cases.py")
    report = {
        "text": b"".join(chunks).decode("utf-8", "surrogatepass"),
        "pid": os.getpid(),
        "sibling": attempt(lambda: read(sibling)),
        "exec": attempt(lambda: os.execv("/usr/bin/true", ["true"])),
        "argv0": sys.argv[0],
    }
    if len(sys.argv) == 4:
        channel = socket.socket(fileno=int(sys.argv[3]))
        message = channel.recv(256)
        channel.send(message[::-1])
        report["channel"] = message.decode()
    os.write(result, json.dumps(report).encode())


if __name__ == "__main__":
    main()
