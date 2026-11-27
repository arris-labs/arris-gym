# CAD-Recode validation census and reach curve

Generated from the original [CAD-Recode corpus](https://huggingface.co/datasets/filapro/cad-recode/tree/17d554bbc50a23de6cf6a742a3e0ed867f000153/val),
revision `17d554bbc50a23de6cf6a742a3e0ed867f000153`, validation only. The pin
contains 968 Python files (the dataset card says approximately 1k). All 968
parse and end in `r = …`. Their family is recorded as `validation` because
the source has no family labels. No source programs are committed.

`programs.jsonl.gz` holds canonical JSON lines in stem order: program SHA-256,
family, census outcome, source, config, revision and licence. Gzip has
`mtime=0`. Every row carries **CC-BY-NC-4.0**. `census.json` holds the
aggregate counts; `reach.json` the curve with the unchanged C1 subset.
Its initial reach is **0/968**: the end form is outside the subset. The curve
admits `r = …` first and reaches 104/968 after four items, 697 after 17 and
all 968 after 20. The sketch forms use the `Sketch` receiver (ADR-0003).
`manifest.json` records the uncompressed rows' SHA-256 and the census and
reach digests. Two complete runs give equal bytes and digests.

To regenerate with the frozen C1 subset, run the census writer from the
repository root with the C1 subset supplied by the offline test:

```sh
PYTHONPATH=tests uv run --locked --extra corpus python - <<'PY'
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import fixture_cases
from arris_gym import _cli
from arris_gym.census import ReachCurve, cadrecode

out = Path(".scratch/cadrecode-census")
with patch.object(_cli, "subset", fixture_cases.c1_subset):
    report = _cli.run_census(cadrecode.read, out, cadrecode.INFO)
rows = gzip.decompress((out / "programs.jsonl.gz").read_bytes())
curve = ReachCurve.from_json((out / "reach.json").read_text())
manifest = {
    "census_digest": report.digest,
    "programs_sha256": hashlib.sha256(rows).hexdigest(),
    "reach_digest": curve.digest,
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
```

These counts, stems and hashes are adapted from CAD-Recode by Danila
Rukhovich, Elona Dupont, Dimitrios Mallis, Kseniya Cherenkova, Anis Kacem and
Djamila Aouada, [CAD-Recode: Reverse Engineering CAD Code from Point
Clouds](https://arxiv.org/abs/2412.14042). They are shared under the source's
[Creative Commons Attribution-NonCommercial 4.0 International licence](https://creativecommons.org/licenses/by-nc/4.0/).
The [pinned source card](https://huggingface.co/datasets/filapro/cad-recode/blob/17d554bbc50a23de6cf6a742a3e0ed867f000153/README.md)
states `license: cc-by-nc-4.0`. These derived artefacts retain that restriction;
the library's code licence does not replace it.


## The table

`fidelity.json.gz` compares all 968 programs under `cq` on arris 0.12.0
with the committed oracle rows from CadQuery 2.3.0 and Open CASCADE 7.9.3.0.
`arris-report.json` and `.md` carry the refusals. `reach-report.json`
checks this table against the census and `cq.subset()`.

Replay the committed oracle reports from the repository root with a fresh
work directory (ADR-0030, outside the gate).

```sh
root=tests/fixtures/c2/cadrecode
work=$(mktemp -d)
mkdir "$work/out"
uv sync --locked --extra corpus
uv run --locked --extra corpus python tools/cq_corpus.py --corpus cadrecode \
  --verdicts "$root/verdicts.json" --replay-oracle-rows "$root/oracle.jsonl.gz" \
  --out-dir "$work/out" --work-dir "$work/chunks" --workers 4 --timeout 30
```

On 2026-11-27, [run 45990557026](https://github.com/arris-labs/arris-gym/actions/runs/45990557026)
tested `1d577e97620336a122099bce4d01f66d7b4abe82` on Linux x86-64 and
aarch64. Both jobs reproduced the fidelity digest and counts below. The
uncompressed oracle rows, reach report and both arris reports matched the
committed contents.
[x86-64 reports](https://github.com/arris-labs/arris-gym/actions/runs/45990557026/artifacts/15195900879) ·
[aarch64 reports](https://github.com/arris-labs/arris-gym/actions/runs/45990557026/artifacts/15196175506)

All counts are over the 968 programs. Reach is **968**, which meets the
CAD-Recode fidelity target (ADR-0014). All 893 agreements are two
successful builds. The 75 disagreements are 56 `arris_refusal` and 19
`occt_wrong`. There are zero `arris_bug`, `cq_bug`, `by_design`,
unclassified or timed-out rows. The oracle ends `ok` on all 968. arris
ends `ok` on 912 and `arris_refusal` on 56.

Table digest: `7cc30ad7c343342e6763224b231790dd9de5f2954d2b7bac3693522dc1246b92`.
The full replay after the BenchCAD shell lift reproduces
the table, reach report, both arris reports and pinned oracle rows
byte-for-byte. The aggregate census and per-program rows also regenerate
byte-for-byte. The census digest is
`3d0c9f1b11519ec7e8109adce9c4f5861826b5722c159494145f2b42fb055170`.

On 0.11.1 the same subset had 873 agreements and digest
`fe2861b7598b1d3e31651641cc00ff7c98f55c4a77394cded62125ebfadf71cc`.
Nineteen formerly refused programs build and agree. The earlier refusals
reported interior face contact on 15 programs and shells touching at an
edge or vertex on four (`167`, `461`, `565`, `899`). Stem `239` also
agrees. Its tangent posts previously left intersecting loops in the cap
(`cq-sketch-post-tangent-to-cap`), and its verdict is retired. The 19
`occt_wrong` verdicts still hold at the same tolerance. The oracle file
is byte-equal to the committed input. Its uncompressed SHA-256 is
`8d28ce1199f0b98f0878bdd63789fcfed2ee2e2648178b9a7289b17f2c1f195f`.

The sketch lift (ADR-0023) raised reach from 104 to 968. The last table
at reach 104 had digest
`e2bf586c6f8970875a98f631d1d2bb645ac69bbaf0f02532f61f8c8932107308`.

## Verdicts

Stem `550` still uses the closed form for two crossing cylinders. Another
18 builds agree with the boundary integral of the oracle's planar and
cylindrical faces. The integral evaluates area and flux through the trim
curves at two resolutions (Green's theorem and the divergence theorem).
It uses the oracle's B-Rep and tight bounds and computes the measures
independently of the oracle's default GProp integration. The comparator
checks each verdict against both sides at the ADR-0005 tolerance.

Regenerate the verdicts from the table with:

```sh
root=tests/fixtures/c2/cadrecode
uv run --locked --extra corpus tools/cq_closed_forms.py --corpus cadrecode \
  --table "$root/fidelity.json.gz" --oracle-rows "$root/oracle.jsonl.gz" \
  --sketch-boundary \
  --out "$root/verdicts.json"
```

## Baseline

The first table had reach 0 and 968 agreements between
`unsupported_api` and `no_result` (digest
`7f19ee794233d27fc3c0d7f0a5f885ae3e5ea65d37bb00fef28a8f95408ea440`).
Both workers then began reading `r = …` (ADR-0015). Reach rose to 37
with the workplane and compound lifts (ADR-0016), then to 104 with
`Workplane.cylinder`. BenchCAD's later lifts left those figures unchanged.
