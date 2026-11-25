# BenchCAD failure verdicts on arris 0.12.0

`failure-replay.txt` lists 190 programs at BenchCAD revision
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
`d7dd81c7fa23ce5af6af928b1a88740718c35b83516204c4cdf454e1e38a16c8`.
When assembling the 0.12.0 baseline, use these verdicts in place of any
historical entries for the same stems. The pinned oracle rows remain the
source of oracle outcomes.

## Overlapping blends

The kernel diagnostic names two selected edges and their shared face. The seven
rows below return `OpDegenerateError`, and the pinned oracle shapes are `invalid`.
The two blends each take one setback from the common planar face. In each row
the setbacks add up to more than the face's radial width.

| Stem | First refused operation | Face width | Combined setback |
|---|---|---:|---:|
| `bucket_002516_s20260505` | lip chamfer | 4.59 | 4.60 |
| `bucket_009912_s20260505` | lip chamfer | 2.76 | 2.80 |
| `pipe_flange_016767_s20260505` | raised rim chamfer | 3.715 | 4.34 |
| `shaft_collar_000653_s20260505` | boss rim fillet | 2.805 | 3.68 |
| `shaft_collar_009380_s20260505` | boss rim fillet at `>X` | 3.660 | 3.86 |
| `shaft_collar_016155_s20260505` | boss rim chamfer at `>Z` | 3.140 | 4.40 |
| `worm_screw_001803_s20260505` | first end chamfer | 1.150 | 1.32 |

The fixtures are `regression/cq-chamfers-overlap-on-a-face` and
`regression/cq-fillets-overlap-on-a-face`. The six formerly unclassified rows
are `arris_refusal`, as is the historical `shaft_collar_016155_s20260505`
whose earlier internal error was classed `arris_bug`. The worm screw remains
outside the subset. Its first chamfer refuses before the helix sweep, and a
fresh oracle run truncated after that chamfer also returns `invalid`.

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
