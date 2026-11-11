"""`tools/cq_corpus.py`'s resume (plans/fidelity-target step 5): a saved chunk is kept
except for its timed-out rows, which are run again (a timeout is never cached)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import cq_corpus
from arris_gym.census import CorpusProgram
from test_fidelity_table import entries


def test_a_resume_reruns_only_the_timed_out_rows() -> None:
    chosen = [e for e in entries() if e.name in ("agree-box", "class-cq-bug")]
    good = [e.model_dump(mode="json") for e in chosen]
    stale = dict(good[1])
    stale["row"] = {**good[1]["row"], "oracle_status": "timeout", "oracle_versions": None}
    oracle: list[dict[str, Any]] = [{"stem": "a"}, {"stem": "stale"}]
    data = {"entries": [good[0], stale], "oracle": oracle}
    part = [CorpusProgram(stem=e.name, family="f", text="") for e in chosen]
    seen: list[str] = []

    def rerun(ps: Sequence[CorpusProgram]) -> dict[str, Any]:
        seen.extend(p.stem for p in ps)
        return {"entries": [good[1]], "oracle": [{"stem": "fresh"}]}

    body, again = cq_corpus.retry_timeouts(part, data, rerun)
    assert again
    assert seen == [chosen[1].name]
    assert body["entries"] == good
    assert body["oracle"] == [{"stem": "a"}, {"stem": "fresh"}]
    # No timeout, no rerun: the saved body is returned as it is.
    body, again = cq_corpus.retry_timeouts(part, {"entries": good, "oracle": oracle}, rerun)
    assert not again
    assert body["entries"] == good
