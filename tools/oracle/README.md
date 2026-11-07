# tools/oracle

CadQuery on Open CASCADE, run out of process on the same programs as `cq` on
arris (`docs/ARCHITECTURE.md` §The oracle). Its own `uv` environment, not in the
gate and never imported by the library (`tools/check_layers.py`). Programs are
untrusted here too: the runner gives them the same limits as the sandbox.

It lands with M2 (`docs/ROADMAP.md`). The contract it is built to:

- pins `cadquery==2.3.0` and `cadquery-ocp==7.9.3.0`, BenchCAD's own, with their
  `numpy<2`;
- takes a program, reports JSON: status, volume, area, centroid, face and solid
  counts, and the versions;
- a crash or hang in Open CASCADE is a report, never a lost row.
