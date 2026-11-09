"""Print the digest of every reward fixture's score: `score_digest_main.py WORKERS`.

Run by tests/test_reward_digest.py in a subprocess with a chosen
`PYTHONHASHSEED`. Each pair of `tests/fixtures/reward/` (the `arris` ones, and
`benchcad-scorer/`'s `cq` ones) is run and scored with WORKERS programs and
scores alive at once; the output is one line per pair, `name digest`, sorted
by name, then the SHA-256 of those lines.
"""

from __future__ import annotations

import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor

import fixture_cases
from arris_gym import ExecResult, Sandbox, Score, Status, score

ROOT = fixture_cases.ROOT / "reward"


def pairs() -> list[tuple[str, str, str, str]]:
    """(name, dialect, program, target) for every fixture pair, sorted by name."""
    found = []
    for folder in sorted(ROOT.iterdir()):
        if (folder / "program.py").is_file():
            found.append((folder.name, "arris", folder))
        elif folder.is_dir() and (folder / "scorer.json").is_file():
            found.extend(
                (f"{folder.name}/{d.name}", "cq", d) for d in sorted(folder.iterdir()) if d.is_dir()
            )
    return [
        (name, dialect, (d / "program.py").read_text("utf-8"), (d / "target.py").read_text("utf-8"))
        for name, dialect, d in sorted(found)
    ]


def main() -> None:
    workers = int(sys.argv[1])
    cases = pairs()
    with Sandbox() as sandbox, ThreadPoolExecutor(workers) as pool:

        def one(case: tuple[str, str, str, str]) -> tuple[str, Score]:
            name, dialect, program, target = case
            candidate: ExecResult = sandbox.run(program, dialect=dialect)
            goal = sandbox.run(target, dialect=dialect)
            assert candidate.status is Status.OK, name
            assert goal.body is not None, name
            scored = score(candidate, goal.body, sandbox=sandbox)
            assert scored.status is Status.OK, (name, scored.message)
            return name, scored

        rows = list(pool.map(one, cases))
    lines = [f"{name} {row.digest()}" for name, row in rows]
    total = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    sys.stdout.write("\n".join([*lines, total]) + "\n")


if __name__ == "__main__":
    main()
