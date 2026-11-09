"""The ten BenchCAD pairs of `tests/fixtures/reward/benchcad-scorer/`, shared by tests.

docs/plans/m4-reward.md step 8: each pair's programs, what BenchCAD's own
scorer answered (`scorer.json`), and our score of the pair.
"""

from __future__ import annotations

import functools
import json

import arris_gym as ag
import fixture_cases

ROOT = fixture_cases.ROOT / "reward" / "benchcad-scorer"
SCORER = json.loads((ROOT / "scorer.json").read_text(encoding="utf-8"))
SLUGS = sorted(d.name for d in ROOT.iterdir() if d.is_dir())


@functools.cache
def ours(slug: str) -> ag.Score:
    """Our `score` of pair `slug`, run once per process."""
    with ag.Sandbox() as sandbox:
        candidate = sandbox.run((ROOT / slug / "program.py").read_text("utf-8"), dialect="cq")
        target = sandbox.run((ROOT / slug / "target.py").read_text("utf-8"), dialect="cq")
        assert target.body is not None
        return ag.score(candidate, target.body, sandbox=sandbox)
