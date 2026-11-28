# ADR-0032: Freeze BenchCAD Vision2Code targets from the pinned regrader's export helper

- Status: accepted
- Date: 2026-11-28

## Context

C3's first model-output comparison starts with the 300 single-solid cases
from C1. ADR-0011 freezes STEP from the arris-gym oracle for the C1 replay.
BenchCAD's materializer and regrader build their own STEP from the
reference program. The Vision2Code corpus revision
`5919f578ab09ec283603a082fab07c7639ab56eb` supplies program text and images.
The materializer at
`77fd16a80a4e5fc39964ee23b6cc3225beefac8f` uses `record_id = stem`.

[Corpus revision](https://huggingface.co/datasets/BenchCAD/BenchCAD/tree/5919f578ab09ec283603a082fab07c7639ab56eb/code_gen) ·
[Pinned materializer](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/Vision2Code/tools/download_codegen_bench.py)

## Decision

Read the pinned `code_gen` corpus and verify every slice ID, family and
reference program SHA-256 against the committed C1 oracle records. Capture
the upstream `execute_cq_to_step` export of each selected reference program
as bytes. Check that Gym imports exactly one valid solid before inference.
Both graders read those bytes. Record their full-file SHA-256 and Gym's
STEP data-section hash (ADR-0011). Generate the canonical
`composite_for_step` four-view PNG from those bytes and hash it too. GPU or
driver choice can change rendered bytes. The pilot captures with Mesa
software EGL and uses the captured PNGs.

For a prediction, the pinned extractor returns the program that both
graders receive. Run the pinned export helper with its own rules for
`result` and `.exportStep`. Send the candidate STEP and the frozen target to
a separate job running `iou_step_vs_step`. Upstream tessellates each body's
STEP at 0.05, centers each mesh at its bounding-box center and scales each
mesh's own longest axis to 1. It fills voxels at pitch 1/64 and pads onto a
68³ grid. Use the regrader's four decimal places per record. Missing,
blank and export failures produce zero. The metric itself can also return
zero after catching an exception, so a reported zero alone leaves the
cause unknown.

[Pinned regrader](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/tools/regrade.py) ·
[Extractor and STEP export](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/benchcad_core/scoring/exec_cq.py) ·
[Voxel IoU](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/benchcad_core/scoring/iou.py) ·
[Canonical views](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/benchcad_core/scoring/views.py)

### Isolation and pins

Each helper call runs out of process under bubblewrap, in fresh user,
PID, mount, network and IPC namespaces, with an unprivileged UID, no
capabilities, no nested user namespace and a cleared environment. A job sees
the read-only system runtime, oracle venv, five upstream files from the
pinned Git object, worker glue and that job's inputs. Its writable scratch
is a private 64 MiB tmpfs. Export receives only program text. STEP parsing,
rendering and scoring run in jobs with read-only STEP inputs. Isolation
setup errors fail the job.

The launcher applies the ADR-0002 seccomp filter, a hard 2.5 GiB address-space
limit per process, 16 tasks in the user namespace and a 32 MiB file size
limit. The host owns a 60 s smoke deadline per job. Killing bubblewrap at
the deadline tears down its PID namespace and the processes still in it.
The helper strips BLAS settings for the export child. The launcher gives
the job affinity to one CPU to keep BLAS imports within the task limit.

The worker's installed packages must match the oracle lock. The environment
uses system CPython 3.12. The lock SHA-256 and versions are recorded with
the smoke, including CPython 3.12.3, CadQuery 2.3.0,
cadquery-ocp 7.9.3.0, NumPy 1.26.4, Trimesh 4.12.2, SciPy 1.17.1, VTK 9.5.2
and Pillow 13.0.0. The smoke host used bubblewrap 0.9.0 and Mesa 25.2.8
software EGL on x86-64. [Smoke record](../../tests/fixtures/benchcad-vision2code/smoke/smoke.json)

## Consequences

- All 300 IDs join to the committed C1 hashes. The first ID in each
  family by stem imported as one valid solid on arris 0.12.0.
- On the frozen exports, the wrapper and pinned regrader both gave 1.0000
  for all three cases. The parity probe gives `regrade_codegen` the raw
  response and supplies the two captured files at its export call sites.
  The regrader's own extractor and metric still run, and the probe checks
  the extracted bytes. Box fixtures also exercise non-unit IoU, a uniformly
  scaled box, missing submissions, and blank and broken programs.
- The target and candidate use the same upstream export helper in separate
  jobs. Fresh exports can change full-file hashes, for example through the
  STEP timestamp. The smoke fixtures retain the actual target and candidate
  bytes consumed, plus the extracted program and canonical render.
- The phone stand clips at the edge of the pinned four-view framing. The
  capture preserves that framing. The smoke's limits and evidence cover the
  three reference programs. C3 measures Gym's limits on model outputs
  separately.

## Alternatives considered

- Use the committed C1 STEPs. Those files were made by the C1 oracle's export
  path. Capturing upstream's export establishes the target actually used by
  the official grader and the four-view render.
- Call the full regrader in one job for each prediction. That rebuilds the
  target and places both programs and the scorer in one writable scratch
  directory. The export and score jobs give each stage its own inputs and
  let the comparison reuse the same frozen target.
