"""The script `tests/test_exec.py` execs to probe the ELF loader's reach (ADR-0004).

Usage: `exec_loader.py PAYLOAD_FD RESULT_FD`, with `LOADER` in the environment.
The exec job may execute the loader, and the loader maps any file it can read,
so it runs readable programs the job may not execute itself. The report says
what that gives a program: `/usr/bin/perl` run directly (refused) and through
the loader printing its uid, and `/usr/bin/bash` through the loader trying to
connect and to write a file, with no fork beyond the loader's own process.

Perl, not `id`: through the loader a program's executable is the loader, and
a multicall coreutils (uutils, on Ubuntu's newer runners) refuses an `id`
whose executable is not named `id`. `perl-base` is Essential on Debian and
Ubuntu and one binary of its own on every machine the gate runs on.
"""

import json
import os
import subprocess
import sys

# Perl's `$<` is getuid(), with no module loaded. Read from stdin: `-e`
# opens `/dev/null` as its script file, which the sandbox does not grant.
PERL = 'print "$<\\n";'
# Bash builtins only: `$UID` is getuid(), and a redirection on `:` is a
# connect (`/dev/tcp`) or an open for writing, each with its own exit code.
SCRIPT = (
    'echo "uid=$UID"; '
    ': 3<>/dev/tcp/192.0.2.1/80; echo "connect=$?"; '
    ': > /tmp/arris-gym-loader-probe; echo "write=$?"'
)


def through_loader(loader: str, *argv: str, stdin: str = "") -> dict[str, object]:
    done = subprocess.run([loader, *argv], input=stdin, capture_output=True, text=True, timeout=10)
    return {"code": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


def main() -> None:
    payload, result = int(sys.argv[1]), int(sys.argv[2])
    while os.read(payload, 1 << 16):
        pass
    loader = os.environ["LOADER"]
    try:
        os.execv("/usr/bin/perl", ["perl"])
    except OSError as e:
        direct = [type(e).__name__, e.errno]
    report = {
        "direct": direct,
        "perl": through_loader(loader, "/usr/bin/perl", stdin=PERL),
        "bash": through_loader(loader, "/usr/bin/bash", "--noprofile", "--norc", "-c", SCRIPT),
    }
    os.write(result, json.dumps(report).encode())


if __name__ == "__main__":
    main()
