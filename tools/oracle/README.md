# tools/oracle

CadQuery on Open CASCADE, run out of process on the same programs as `cq` on
arris (`docs/ARCHITECTURE.md` §The oracle). Its own `uv` environment, not in the
gate and never imported by the library (`tools/check_layers.py`). Programs are
untrusted here too: each runs in an **oracle worker**, a program worker under
the sandbox's warden that execs this environment's interpreter on
`worker.py` with the sandbox's limits (ADR-0004). It lands with M2
(`docs/ROADMAP.md`). The contract it is built to:

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

`worker.py` also creates Open CASCADE's thread pool with one thread before any
program runs: cadquery runs every boolean in parallel on it, and a pool of
one thread per processor hangs under the worker's `RLIMIT_NPROC` (ADR-0004).

## The worker

As the oracle worker, `worker.py PAYLOAD_FD RESULT_FD` reads the program from
the payload descriptor and writes one JSON report to the result descriptor;
`tools/oracle_run.py` builds its exec spec and sends the job. By hand, for a
trusted program only, `worker.py PROGRAM.py` prints the report. STEP is
written to memory (an oracle worker writes no file), and `step_sha256` hashes
its data section with the per-process translator counter blanked.

## Checks

Neither is in the gate, which runs without this environment:

- `uv run --project tools/oracle tools/oracle/selftest.py`: trusted programs,
  unisolated, against their closed forms;
- `uv run pytest -m oracle`: M0's hostile programs on the oracle worker give
  their outcomes under ADR-0004's limits (`tests/test_oracle_worker.py`).
