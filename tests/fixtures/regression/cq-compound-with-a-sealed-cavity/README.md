# cq-compound-with-a-sealed-cavity

A box with a sealed cylindrical cavity touches a torus at one point,
as in `torus_link_000400_s20260505` from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
The box's remaining material and the torus are two solids. The box has an
outer shell and a cavity shell, and the torus adds the third shell.

The recorded CadQuery 2.3.0 report (`uv run tools/oracle_run.py` on this
program) counts two solids. On arris 0.12.0, the program returns three
shells, two solids and measures within the ADR-0005 tolerance of the
oracle's. The fidelity row is `agree` under ADR-0016.
`tests/test_cq_compound.py` tests that a changed solid count or a measure
gap makes the row `unclassified`.
