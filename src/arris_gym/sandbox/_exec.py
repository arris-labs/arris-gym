"""The exec job: a program worker that execs another interpreter (ADR-0004).

The oracle runs CadQuery on Open CASCADE in an environment of its own, which
cannot be imported into a zygote (ADR-0004). So its program worker is forked
and isolated exactly as any other (`sandbox/_isolate.py`, ADR-0002), and only
then `execve`s the interpreter an `ExecSpec` names. The exec keeps every limit:
the namespaces, the rlimits, `no_new_privs`, the Landlock domain and the
seccomp filter all survive it. The Landlock domain lets `execve` reach the
interpreter and its ELF loader alone, but that is not a boundary: the loader
maps any file the domain reads, and Landlock cannot refuse `mmap` with
`PROT_EXEC`, so the program can run any readable program through the loader.
Whatever it runs keeps the same namespaces (uid nobody, no network), rlimits,
seccomp filter, Landlock domain and read-only mounts (ADR-0004).

The job's payload is the spec and the program's text in one descriptor:
a length, the spec as JSON, then the text (`payload`). The zygote reads the
spec (`read_spec`), which leaves the descriptor's offset at the text; the
executed script reads the text from the descriptor whose number ends its
argv, and writes its one frame to the result descriptor named after it.
Nothing the script writes is trusted by the caller. Private.
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass

# The payload's first bytes: the spec's length in bytes.
_LENGTH = struct.Struct("<I")
# A spec is a few paths; one this long is a caller's bug, refused unread.
MAX_SPEC_BYTES = 1 << 20

# ELF (include/uapi/linux/elf.h): the 64-bit header's program-header table
# and the PT_INTERP entry naming the loader. Both supported machines are
# little-endian 64-bit.
_ELF_MAGIC = b"\x7fELF"
_ELFCLASS64 = 2
_ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
_PROGRAM_HEADER = struct.Struct("<IIQQQQQQ")
_PT_INTERP = 3

# What the interpreter is asked for its own reach: its prefixes and every
# site-packages directory, as `_isolate.readable_roots` takes the zygote's.
_ROOTS_QUERY = (
    "import json, site, sys; print(json.dumps([sys.prefix, sys.exec_prefix, "
    "sys.base_prefix, sys.base_exec_prefix, *site.getsitepackages()]))"
)
# How long the trusted query may take: an interpreter's start-up, with margin.
_QUERY_TIMEOUT = 30.0
# A line of the ELF loader's `--list` (what `ldd` prints) naming a library it
# found: `name => /path (0x...)`, or `/path (0x...)` for the loader itself.
# The vDSO has no path, and `name => not found` none either.
_LISTED = re.compile(r"^\s*(?:\S+ => )?(/.*) \(0x[0-9a-f]+\)$")


@dataclass(frozen=True)
class ExecSpec:
    """What an exec job's worker runs, and what it may read and execute.

    `argv[0]` is the interpreter as it is called (a virtual environment's
    `bin/python`, whose path tells the interpreter its environment), the rest
    its arguments; the payload and result descriptors' numbers are appended.
    `env` is the whole environment: nothing of the zygote's is passed.
    `readable` are the directories or files the worker may read beneath,
    the shared libraries the interpreter links among them;
    `executable` the files `execve` may reach, the interpreter's real path
    and its ELF loader; the loader then runs anything readable (ADR-0004).
    All paths are absolute.
    """

    argv: tuple[str, ...]
    env: tuple[tuple[str, str], ...]
    readable: tuple[str, ...]
    executable: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("an exec spec names an interpreter")
        for path in (self.argv[0], *self.readable, *self.executable):
            if not os.path.isabs(path):
                raise ValueError(f"an exec spec's paths are absolute, not {path!r}")


def elf_loader(executable: str) -> str | None:
    """The real path of the ELF loader `executable` names, or None if static."""
    with open(executable, "rb") as f:
        header = _ELF_HEADER.unpack(f.read(_ELF_HEADER.size))
        ident, phoff, phentsize, phnum = header[0], header[5], header[9], header[10]
        if ident[:4] != _ELF_MAGIC or ident[4] != _ELFCLASS64:
            raise ValueError(f"{executable} is not a 64-bit ELF executable")
        for i in range(phnum):
            f.seek(phoff + i * phentsize)
            kind, _, offset, _, _, size, _, _ = _PROGRAM_HEADER.unpack(f.read(_PROGRAM_HEADER.size))
            if kind == _PT_INTERP:
                f.seek(offset)
                return os.path.realpath(f.read(size).rstrip(b"\0").decode())
    return None


def shared_libraries(executable: str, loader: str, env: Mapping[str, str]) -> tuple[str, ...]:
    """The real paths of the shared libraries `loader` maps to start `executable`.

    The loader's own `--list` (a trusted run, `ldd`'s), under the environment
    the exec gets. A system interpreter's libraries sit beneath its prefix
    `/usr`; a standalone build's (uv's) do not, so without them the exec ends
    127 before the interpreter runs. A library the loader does not find is
    left out, and the exec then ends with the loader's own message. Raises
    `subprocess.CalledProcessError` or `OSError` if the loader cannot run.
    """
    done = subprocess.run(
        [loader, "--list", executable],
        env=dict(env),
        capture_output=True,
        check=True,
        timeout=_QUERY_TIMEOUT,
        text=True,
    )
    found = (m.group(1) for line in done.stdout.splitlines() if (m := _LISTED.match(line)))
    return tuple(sorted({os.path.realpath(p) for p in found if os.path.isfile(p)}))


def interpreter_spec(python: str, script: str, env: Mapping[str, str]) -> ExecSpec:
    """The spec that runs `script` on the interpreter `python`, isolated.

    `python` is asked for its prefixes and site-packages (a trusted run, no
    program in it); those, the shared libraries its loader maps for it
    (`shared_libraries`) and `script` are the worker's whole reach, and
    the interpreter's real path and its loader all `execve` may reach. The
    interpreter runs with `-s -P -B`: no user site, no script directory on
    `sys.path`, no bytecode written. Raises `subprocess.CalledProcessError`
    or `OSError` if `python` cannot be run.
    """
    python = os.path.abspath(python)
    script = os.path.realpath(script)
    done = subprocess.run(
        [python, "-s", "-P", "-c", _ROOTS_QUERY],
        env=dict(env),
        capture_output=True,
        check=True,
        timeout=_QUERY_TIMEOUT,
        text=True,
    )
    prefixes: list[str] = json.loads(done.stdout)
    real = os.path.realpath(python)
    loader = elf_loader(real)
    libraries = shared_libraries(real, loader, env) if loader else ()
    roots = {os.path.realpath(p) for p in prefixes if os.path.isdir(p)} | {script, *libraries}
    return ExecSpec(
        argv=(python, "-s", "-P", "-B", script),
        env=tuple(sorted(env.items())),
        readable=tuple(sorted(roots)),
        executable=tuple(sorted({real} | ({loader} if loader else set()))),
    )


def payload(spec: ExecSpec, text: bytes) -> bytes:
    """An exec job's payload: the spec's length, the spec as JSON, the text."""
    encoded = json.dumps(
        {
            "argv": spec.argv,
            "env": spec.env,
            "readable": spec.readable,
            "executable": spec.executable,
        }
    ).encode()
    return _LENGTH.pack(len(encoded)) + encoded + text


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("not a list of strings")
    return tuple(value)


def read_spec(fd: int) -> ExecSpec | None:
    """The spec at the start of payload `fd`, leaving its offset at the text.

    None when the payload holds no whole, valid spec: a caller's bug, since
    only the caller writes a payload.
    """
    try:
        head = os.read(fd, _LENGTH.size)
        if len(head) != _LENGTH.size:
            return None
        (length,) = _LENGTH.unpack(head)
        if length > MAX_SPEC_BYTES:
            return None
        data = b""
        while len(data) < length and (chunk := os.read(fd, length - len(data))):
            data += chunk
        fields = json.loads(data)
        env = fields["env"]
        if not isinstance(env, list) or not all(isinstance(p, list) and len(p) == 2 for p in env):
            return None
        return ExecSpec(
            argv=_strings(fields["argv"]),
            env=tuple((k, v) for k, v in (_strings(p) for p in env)),
            readable=_strings(fields["readable"]),
            executable=_strings(fields["executable"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def execute(spec: ExecSpec, payload_fd: int, result_fd: int, *channel: int) -> None:
    """Exec the spec's interpreter with the job's descriptors; never returns.

    Called inside an isolated program worker. The payload, the result and
    the job's channel if it has one (ADR-0013) are kept across the exec at
    their numbers, which end the argv in that order. A failed exec raises,
    so the worker ends with no frame.
    """
    kept = (payload_fd, result_fd, *channel)
    for fd in kept:
        os.set_inheritable(fd, True)
    argv = [*spec.argv, *(str(fd) for fd in kept)]
    os.execve(spec.argv[0], argv, dict(spec.env))
