# BenchCAD's scorer on ten pairs

Each `<slug>/` holds `program.py` and `target.py`, both `cq`-dialect programs
that run on arris-gym's `cq` and on CadQuery 2.3.0. `scorer.json` is what
BenchCAD's own scorer answered on their STEP: `compute_iou`, `compute_chamfer`
(100 draws, since theirs is unseeded) and `iou_step_vs_step`, from
`BenchCAD-main@77fd16a8` (MIT), with trimesh 4.12.2 and scipy 1.17.1.

Regenerate (network; not in the gate), from the repository root:

    uv run --project tools/oracle tools/oracle/benchcad_score.py

The tolerance the field is held to, how it was measured and why, is
ADR-0010 (`docs/adr/0010-*.md`); `tests/test_reward_benchcad.py` holds it. The
programs are our own: none comes from a corpus. A pair of one shape twice
(`box-and-double`, `box-shifted`, `plate-self`) gives their Chamfer a
nonzero floor and ours exactly 0. `cone-pair` is a cone against a cone, which
the kernel refuses, so our IoU on it is sampled.
