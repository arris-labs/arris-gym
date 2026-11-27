#!/usr/bin/env python3
"""Check C2 fidelity replay reports against the committed reports and acceptance."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path

from arris_gym.fidelity import FidelityTable, ReachReport

# Program counts and minimum reach (ADR-0014), and the allowed by_design rows
# for the two BenchCAD corner patches (ADR-0025).
ACCEPTANCE = {"benchcad": (17_900, 15_215, 2), "cadrecode": (968, 968, 0)}
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "c2"


def main(argv: Sequence[str] | None = None) -> int:
    """Print the replay's counts and digests, and return 1 if any check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", choices=ACCEPTANCE, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument(
        "--reference-dir", type=Path, help="defaults to the committed corpus reports"
    )
    args = parser.parse_args(argv)
    reference: Path = args.reference_dir or FIXTURES / args.corpus
    replay: Path = args.replay_dir
    with gzip.open(reference / "fidelity.json.gz", "rt", encoding="utf-8") as table:
        expected = FidelityTable.from_json(table.read())
    with gzip.open(replay / "fidelity.json.gz", "rt", encoding="utf-8") as table:
        actual = FidelityTable.from_json(table.read())
    reach = ReachReport.model_validate_json((replay / "reach-report.json").read_bytes())
    print(f"committed table digest: {expected.digest}")
    print(f"replayed table digest:  {actual.digest}")
    print(
        f"programs={actual.programs} in_subset={reach.in_subset} agree={actual.outcomes['agree']} "
        f"unclassified={actual.outcomes['unclassified']} timeouts={len(actual.timed_out)} "
        f"in_subset_cq_bug={reach.in_subset_cq_bug} in_subset_by_design={reach.in_subset_by_design}"
    )

    pinned_oracle = gzip.decompress((reference / "oracle.jsonl.gz").read_bytes())
    replayed_oracle = gzip.decompress((replay / "oracle.jsonl.gz").read_bytes())
    print(f"committed oracle digest: {hashlib.sha256(pinned_oracle).hexdigest()}")
    print(f"replayed oracle digest:  {hashlib.sha256(replayed_oracle).hexdigest()}")
    differences = []
    if expected.digest != actual.digest:
        differences.append("fidelity.json.gz")
    if pinned_oracle != replayed_oracle:
        differences.append("oracle.jsonl.gz")
    for report in ("reach-report.json", "arris-report.json", "arris-report.md"):
        if (reference / report).read_bytes() != (replay / report).read_bytes():
            differences.append(report)
    if differences:
        print(
            "Reports differ from the committed fixtures: " + ", ".join(differences), file=sys.stderr
        )

    programs, minimum_reach, allowed_by_design = ACCEPTANCE[args.corpus]
    fails_acceptance = (
        actual.programs != programs
        or reach.programs != programs
        or reach.in_subset < minimum_reach
        or actual.outcomes["unclassified"] > 0
        or bool(actual.timed_out)
        or reach.in_subset_cq_bug > 0
        or reach.in_subset_by_design > allowed_by_design
    )
    if fails_acceptance:
        print(f"Replay does not meet C2 acceptance for {args.corpus}", file=sys.stderr)
    return 1 if differences or fails_acceptance else 0


if __name__ == "__main__":
    sys.exit(main())
