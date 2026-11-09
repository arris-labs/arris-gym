# ADR-0010: The field metrics agree with BenchCAD's scorer within a voxel tolerance of 0.04, and a Chamfer floor of 2.0 plus a tenth

- Status: accepted
- Date: 2026-11-09

## Context

The field's `voxel_iou_64` and `chamfer_x1000` (`reward/_field.py`) are
BenchCAD's metrics, reimplemented on numpy over the kernel's own mesh
(plans/m4-reward step 7). Their value is that a number here compares with a
published one, so it has to be held against BenchCAD's scorer itself, on the
same programs, with a tolerance measured and not chosen.

`tools/oracle/benchcad_score.py` ran `compute_iou`, `iou_step_vs_step` and
`compute_chamfer` of `BenchCAD-main@77fd16a8` (MIT; files pinned by SHA-256 in
the tool) on 10 pairs of `cq` programs, `tests/fixtures/reward/benchcad-scorer/`
(our own, so no corpus program reaches the oracle), each exported by cadquery
2.3.0 to STEP as their scorer reads it, with trimesh 4.12.2 and scipy 1.17.1.
Their Chamfer draws unseeded surface samples, so it ran 100 times per pair; their
voxel IoU is deterministic (2 runs, equal) and `iou_step_vs_step` returned
`compute_iou`'s value on all ten. Ours ran on the same programs in the `cq`
dialect on arris 0.10.0.

| Pair | voxel: ours | theirs | Chamfer ×1000: ours | theirs mean | sd |
|---|---|---|---|---|---|
| box-and-double (one shape twice) | 1.0000 | 1.0000 | 0.000 | 1.831 | 0.042 |
| box-shifted (one shape twice) | 1.0000 | 1.0000 | 0.000 | 0.765 | 0.019 |
| plate-self | 1.0000 | 1.0000 | 0.000 | 0.601 | 0.014 |
| plate-with-hole | 0.9520 | 0.9484 | 0.856 | 1.144 | 0.043 |
| cone-pair | 0.7649 | 0.7626 | 4.882 | 5.166 | 0.098 |
| ring-and-plate | 0.6116 | 0.6173 | 7.997 | 7.780 | 0.233 |
| frustum-and-cylinder | 0.5929 | 0.5909 | 22.339 | 22.652 | 0.387 |
| cylinder-and-box | 0.7633 | 0.7946 | 12.369 | 11.069 | 0.282 |
| cylinder-heights | 0.4547 | 0.4531 | 34.968 | 37.811 | 0.407 |
| l-bracket | 0.4225 | 0.4225 | 58.956 | 60.479 | 2.296 |

Two differences, kept apart:

- **The Chamfer floor.** Two independent samplings of one surface are never
  at distance 0 (ADR-0009's noise floor, here at 2,048 surface samples): theirs on a
  body against its own shape is 0.60 to 1.83. Ours draws both bodies from
  `PCG64(seed)`, so one shape twice is exactly 0, and plans/m4-reward step 7
  holds it so. Drawn from independent seeds (40 draws per pair, a probe, not
  in the gate) our Chamfer gives 1.838, 0.765 and 0.603 on those three pairs
  and, on the others, 1.104, 4.985, 7.971, 22.584, 12.603, 35.314 and 60.833,
  each within 6.5% of their mean; the floor is then the whole difference on
  the pairs of one shape.
- **The meshes.** Open CASCADE's and the kernel's tessellations of a curved
  surface differ at the same absolute chord of 0.05, so a few surface voxels
  and a few percent of the Chamfer differ. The largest voxel gap is 0.0312
  (`cylinder-and-box`); past the floor, the largest Chamfer gap is 0.84 on
  37.8, 2.2% (`cylinder-heights`).

## Decision

**The field agrees with BenchCAD's scorer, on a pair, when**

- `|voxel_iou_64 − theirs| ≤ 0.04`, their value being deterministic; and
- `|chamfer_x1000 − mean of theirs| ≤ 2.0 + 0.10 · mean of theirs`.

**2.0 is the floor**: the largest of their one-shape pairs' mean plus four
standard deviations over 100 draws is 1.9986, rounded up. **0.10 is the
mesh term**: four and a half times the 2.2% measured; **0.04** is the 0.0312
rounded up to the next hundredth. None of the 10 pairs is outside, so there is
no regression fixture; a pair outside is one, with the desired assertion
(`.agents/rules/gym.md`), never a wider number here. `tests/test_reward_benchcad.py`
holds all of this, and that the floor stays above their noise on the
committed draws.

The tolerance is a statement about *agreement with their scorer on these
programs*, not a claim that the metric is identical: the Chamfer here is
seeded, so a body against itself is 0 where theirs is not, by design.

## Consequences

- A published `voxel_iou_64` and a number from this field differ by up to 0.04
  where a curved surface is meshed; on planar parts they were equal in 9 of 10
  pairs to the digit shown above or within 0.004.
- A reader comparing `chamfer_x1000` with a published one adds the floor: a
  near-perfect candidate scores 0.0 here and 0.6 to 1.8 there.
- A new arris release, a new trimesh, or another BenchCAD commit re-runs the
  tool and the test; `scorer.json` is regenerated only with a plan.
- The Chamfer's tolerance is wide beside the voxel's: it does not say the
  Chamfer is imprecise, but that a seeded and an unseeded sampling differ
  by a floor that depends on the shape.

## Alternatives considered

- **Independent seeds for the two bodies**: matches their sampling and their
  floor, but a body against itself is no longer exactly 0, which M4's closed
  forms and the digest rely on.
- **A tolerance per pair**: fits every pair, says nothing about the next.
- **Fewer repeats**: the spread of their sampling (sd up to 2.3 on `l-bracket`)
  is what the floor and the draws' mean rest on; 100 draws put the standard
  error of a mean under 0.23.
- **Their scorer on corpus programs**: needs a corpus program on an
  unisolated interpreter; the pairs here are ours.
