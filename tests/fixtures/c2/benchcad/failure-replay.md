# BenchCAD failure verdicts on arris 0.12.0

`failure-replay.txt` lists 197 programs at BenchCAD revision
`5919f578ab09ec283603a082fab07c7639ab56eb` and the reduced fixture for each.
The generator reruns arris, checks the program hash against the pinned oracle
report, and verifies the status pair and the fixture's failure signature before
passing the verdict to `compare` under ADR-0006.

```sh
root=tests/fixtures/c2/benchcad
uv run --locked --extra corpus tools/cq_closed_forms.py \
  --failure-replay "$root/failure-replay.txt" \
  --oracle-rows "$root/oracle.jsonl.gz" --out "$root/failure-verdicts.json"
```

Two runs give the same file, SHA-256
`4172ef8bc090b8f93cf649d52618dd8483686e6ab8882236f0b83765dee2cfd3`.
The full 0.12.0 baseline uses the same checks through `--failure-replay`
in `verdicts.args`. These verdicts replace historical entries for the same
stems. The pinned oracle rows remain the source of oracle outcomes.

## Overlapping blends

The kernel diagnostic names two selected edges and their shared face. The 14
rows below return `OpDegenerateError`, and the pinned oracle shapes are `invalid`.
The two blends each take one setback from the common planar face. In each row
the setbacks add up to more than the face's radial width.

| Stem | First refused operation | Face width | Combined setback |
|---|---|---:|---:|
| `bucket_002516_s20260505` | lip chamfer | 4.59 | 4.60 |
| `bucket_009912_s20260505` | lip chamfer | 2.76 | 2.80 |
| `cam_000896_s20260505` | boss rim chamfer at `>Z` | 2.205 | 3.02 |
| `cam_001249_s20260505` | boss rim fillet at `>Z` | 2.455 | 2.62 |
| `cam_004951_s20260505` | boss rim chamfer at `>X` | 2.570 | 3.94 |
| `cam_007606_s20260505` | boss rim chamfer at `>Z` | 1.795 | 2.90 |
| `cam_011690_s20260505` | boss rim chamfer at `>X` | 3.480 | 3.62 |
| `cam_015660_s20260505` | boss rim fillet at `<Y` | 2.510 | 3.46 |
| `pipe_flange_016767_s20260505` | raised rim chamfer | 3.715 | 4.34 |
| `shaft_collar_000653_s20260505` | boss rim fillet | 2.805 | 3.68 |
| `shaft_collar_009380_s20260505` | boss rim fillet at `>X` | 3.660 | 3.86 |
| `shaft_collar_016155_s20260505` | boss rim chamfer at `>Z` | 3.140 | 4.40 |
| `shaft_collar_017314_s20260505` | boss rim chamfer at `>Z` | 2.055 | 2.54 |
| `worm_screw_001803_s20260505` | first end chamfer | 1.150 | 1.32 |

The fixtures are `regression/cq-chamfers-overlap-on-a-face` and
`regression/cq-fillets-overlap-on-a-face`. The six formerly unclassified rows
are `arris_refusal`. The six cams and two collars previously classed
`arris_bug` also receive `arris_refusal`. Prefix runs of the six cams
and `shaft_collar_017314_s20260505` build before the rim blend and refuse
at the blend.
The worm screw remains outside the subset. Its first chamfer refuses
before the helix sweep, and a fresh oracle run truncated after that
chamfer also returns `invalid`.

## Cotter pins and bearing retainer caps

All 159 `cotter_pin` programs build the first union of the two tangent
cylinders. Their union with the half horn-torus head pinches the boundary
along the arms' common line. The 121 self-contact refusals cite
`regression/cq-cotter-pin-self-contact`. The 38 tangent-face refusals cite
`regression/cq-cotter-pin-tangent-faces`. Both reduced programs reproduce
the typed refusal and an invalid oracle shape.

All 24 `bearing_retainer_cap` checker failures reproduce at the first
union of the curved plate and central cylinder. The union alone reports one,
two or four self-intersecting loops. Seven of the 24 programs reproduce four
loops with both opposing plate arcs present. Reducing to one near-tangent
arc preserves the failure in `regression/cq-retainer-plate-arc-loop-intersection`.
Its strict xfail expects a valid solid. The full rows already class as
`arris_bug` under ADR-0006. The verdicts attach the verified fixture.
