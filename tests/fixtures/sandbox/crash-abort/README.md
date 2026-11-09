# crash-abort

A program that writes its last words to stderr and calls `os.abort()`, as a
kernel abort does: `crash`, with the stderr tail in the message.

Its message is declared per machine (`message_by_machine` in `expected.json`,
resolved by `tests/fixture_cases.py`'s `for_machine`), the one sandbox fixture
that is. The program worker is PID 1 of its PID namespace (ADR-0002), to which
the kernel does not deliver the `SIGABRT` that `abort` raises. glibc then
executes its abort instruction, and what that instruction ends the process by
is the machine's:

| `platform.machine()` | instruction | signal |
|---|---|---|
| `x86_64` | `hlt` | `SIGSEGV` |
| `aarch64` | `brk` | `SIGTRAP` |

No program makes an `abort` portable, and `abort` is this fixture's subject
(`crash-segfault` covers a null read, which faults by `SIGSEGV` on both). The
human decided to keep `abort` with an expectation per machine (plans/m5-rescore
step 9) rather than have the worker turn it into one ending. A machine with no
entry fails to load the sandbox fixtures: it is never a silent pass. A new
machine gets its entry from running the program there and reading the signal
against its glibc's abort instruction.
