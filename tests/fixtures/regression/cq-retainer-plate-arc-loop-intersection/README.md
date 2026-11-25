# cq-retainer-plate-arc-loop-intersection

Reduced from `bearing_retainer_cap_013795_s20260505` of
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen`,
revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
The central cylinder and a plate with one nearly tangent arc still
fail the checker after their union. Straight chords replace three arcs,
and the later cuts are omitted. The desired status is `ok`.

CadQuery 2.3.0 builds one solid, recorded in `oracle.json` by
`uv run tools/oracle_run.py` on the reduced program. On arris 0.12.0
the checker reports `loop 0 intersects itself` on two faces. The
full corpus program also returns intersecting loops in fresh runs on
both arris 0.11.1 and 0.12.0, though the recorded 0.11.1 table says
`ok`.
