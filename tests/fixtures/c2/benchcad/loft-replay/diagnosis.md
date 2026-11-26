# BenchCAD loft, taper and mirror replay diagnosis

The stem lists are derived from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` and
shared under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

The full replay ran 17,900 programs after the three lifts at `3385b80`,
using arris 0.12.0, the baseline verdicts and the pinned oracle reports.
The replay oracle file is byte-identical to the committed oracle file
with uncompressed SHA-256
`db298f073af368bc5a73f6856134cd0c8bcafa4bb3a9f6a7911de668fd49136b`.
The table digest is
`e0ffad652b48c94541d96ef30e1606b15851991c4886598710561e087ccb0feb`.

Against the 0.12.0 baseline, 1,179 row payloads changed and 16,721 are
equal. Reach increased from 14,150 to 15,718. The 392 newly reached
gear programs still have the same `cq_bug` rows as the baseline.

| Baseline outcome or class | Replay outcome or class | Rows |
|---|---|---:|
| `cq_bug` | agreement | 832 |
| `cq_bug` | `arris_refusal` | 117 |
| `cq_bug` | unclassified | 227 |
| `occt_wrong` | `occt_wrong` with candidate timeout | 3 |

The replay totals are 12,523 agreements, 5,150 disagreements and 227
unclassified rows. Disagreements comprise 2,573 `cq_bug` (392 in-subset),
887 `arris_refusal`, 321 `arris_bug`, 1,367 `occt_wrong` and 2
`by_design`. The inherited sprocket verdicts retain those three classes
in the table while each row still records the candidate timeout.

Reproduce the representative stem slice from the repository root.

```sh
root=tests/fixtures/c2/benchcad
work=$(mktemp -d .scratch/loft-diagnosis.XXXXXX)
uv run --locked --extra corpus tools/cq_corpus.py --corpus benchcad \
  --verdicts "$root/verdicts.json" --oracle-rows "$root/oracle.jsonl.gz" \
  --slice "$root/loft-replay/diagnostic-stems.txt" \
  --out-dir "$work/out" --work-dir "$work/chunks" --workers 4
```

All 26 slice rows match the full replay. The slice digest is
`c34c7f694cbd3643969410ab83cea24554206cc4c7b65edd6a132090444e60ce`.
Two outside-subset propellers serve as controls for the static reach labels.

| Replay finding | Reduced regression or control |
|---|---|
| 189 bevel gears and 110 two-section helical gears refuse the curved side count | `cq-loft-over-curved-side-limit` and the neighboring count in `lofts/runtime-contexts.json` |
| 93 three-section helical gears need interpolation evidence | `arris-loft-three-tooth-outlines` and the three-section subset guard in `test_cq_loft.py` |
| Two I-beam through bores fail in a filleted flange | `cq-filleted-beam-through-bore` |
| One knob's flute is tangent to its axial bore | `oracle-tangent-knob-cuts` |
| 114 wing-nut refusals against an oracle solid, and 12 analogous refusals against an invalid oracle shape | `cq-wing-nut-bore-fillet-corner` |
| One wing nut fails at a different fillet corner against an invalid oracle shape | `cq-wing-fillet-missing-trim-edge` |
| 41 propellers and four gussets have excess bounds | `cq-turned-blade-prism-bounds` and `cq-mirrored-gusset-chamfer-bounds` |
| Three I-beams and one gusset have measure gaps after boring blended stock | `oracle-filleted-beam-bore` and `oracle-filleted-gusset-bore` |
| 150 drafted knobs have measure gaps after flute cuts | `oracle-draft-knob-first-cut` and `oracle-draft-knob-overlapping-flutes` |
| 15 further propellers have mass-property gaps | One four-blade reduction is in `cq-propeller-hub-blade-measures` |

The beam, gusset and propeller measurement references integrate the
oracle's planar, cylindrical, conical and toroidal trimmed boundary
under ADR-0006. Polar and section geometry independently establish the
two bounds regressions. The reduced evidence identifies where the gaps
start. Full-program verdicts require checking the full-program geometry.

The three candidate timeouts were
`double_simplex_sprocket_009108_s20260505`,
`double_simplex_sprocket_009154_s20260505` and
`double_simplex_sprocket_011623_s20260505`. The one-worker stem slice
recovered the first two and a separate single-stem run recovered the
third under the same 30 s deadline. They reproduce the existing
sprocket performance finding in BACKLOG. The full replay still counts
all three timeouts.
