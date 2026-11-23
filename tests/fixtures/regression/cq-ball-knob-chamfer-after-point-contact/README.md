# cq-ball-knob-chamfer-after-point-contact

Shrunk from the 78 `ball_knob` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) that write a blend (all 78 ended `arris_refusal` in the 0.11.1 baseline); `ball_knob_000446_s20260505` as written: a sphere unioned with a stem whose end disc touches its pole, then `faces("<Z").edges().chamfer(1.35)`.
arris 0.10.0 refuses the union (the point contact of `cq-sphere-pole-on-disc`), so the chamfer never runs; CadQuery 2.3.0 builds the compound and bevels the stem's far rim, V = 46155.2671 (the oracle's), equal to the closed form of `expected.json`'s `note` to 1e-9 (volume, area, centroid z).

Desired: `ok`, that closed form (ADR-0016). The ask is `../arris/docs/ideas/fuse-contact-refusals.md`'s, which
already counts the `ball_knob` programs.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.
