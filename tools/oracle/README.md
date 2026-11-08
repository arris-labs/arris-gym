# tools/oracle

CadQuery on Open CASCADE, run out of process on the same programs as `cq` on
arris (`docs/ARCHITECTURE.md` §The oracle). Its own `uv` environment, not in the
gate and never imported by the library (`tools/check_layers.py`). Programs are
untrusted here too: the runner gives them the same limits as the sandbox.

It lands with M2 (`docs/ROADMAP.md`); step 1 is the environment, `worker.py`
(unisolated) and `selftest.py`. The contract it is built to:

- pins `cadquery==2.3.0` and `cadquery-ocp==7.9.3.0`, BenchCAD's own, with their
  `numpy<2`;
- takes a program, reports JSON: status, volume, area, centroid, face and solid
  counts, and the versions;
- a crash or hang in Open CASCADE is a report, never a lost row.

## The environment

`uv sync --project tools/oracle` (Python 3.12). Both pins resolve with no
override: cadquery 2.3.0 imports on OCP 7.9.3.0. But the cadquery wheel
declares no runtime dependencies, so `pyproject.toml` lists the ones its
source imports (`typing_extensions`, `multimethod`, `typish`, `nptyping`,
`ezdxf`, `casadi`, `nlopt`), unpinned beyond `numpy<2`; `uv.lock` fixes them.

cadquery 2.3.0 calls `TopoDS_Shape.HashCode()`, which OCP 7.9 removed, so
every selector (`faces`, `edges`) raised `AttributeError`. `worker.py`
patches `cq.Shape.hashCode` to `hash(wrapped)` (equal for `IsSame` shapes)
and nothing else.

`worker.py PROGRAM.py` prints one JSON report. `step_sha256` hashes STEP's
data section with the per-process translator counter blanked. Check the
closed forms with `uv run --project tools/oracle tools/oracle/selftest.py`.
