# ADR-0011: A target is the oracle's STEP, read in a step worker and committed

- Status: accepted
- Date: 2026-11-09

## Context

M5 (`docs/ROADMAP.md`) scores each of the C1 slice's 300 programs, run under
`cq`, against a target, and claims the table's digest equal on two machines.
The target has to come from the oracle: a target built by `cq` would score
`cq` against itself. Until now the oracle sent back only a STEP's hash
(`step_sha256`, ADR-0004), so the caller had no target to read.

Three questions follow. How the STEP crosses from the oracle worker to the
caller. Where arris reads it, given that it was produced by a hostile program.
And whether the second machine regenerates it, which would put Open
CASCADE's own cross-machine behaviour inside the claim.

Measured on this machine (AMD Ryzen 9 7950X, x86-64, glibc 2.39, arris
0.10.0) on the 300 slice programs:

| Probe | Result |
|---|---|
| the oracle's STEP of each program, read by `Model.read_step` | 300 of 300 one solid, no healing reported, `check(body, "full")` ok |
| `read_step`'s time per STEP | at most 0.07 s |
| the 200 `ok` programs under `cq`, scored against their targets | IoU 1.0 on all 200; 35 s on 8 workers |
| the STEP header, two runs of one program | differs: `FILE_NAME`'s second argument is a timestamp, and the product name carries a per-process counter (`translator 7.9 2`) |
| the same STEP with the timestamp and the counter blanked | the same bytes on every run |
| `step_sha256` recomputed from the blanked text's data section | equal to the hash the worker sent before this change, on all 300: `oracle.jsonl` is byte-identical |
| the 300 blanked texts, gzip | about 1.5 MB |

## Decision

**The oracle worker sends the STEP back.** Its frame gains `step_text`: the
STEP that `step_sha256` hashes, with `FILE_NAME`'s timestamp and the
translator counter blanked, set exactly when the status is `ok`. The caller
recomputes `step_sha256` from the text's data section (from `DATA;` on), as
the worker does. A text whose hash contradicts the frame's `step_sha256` is a
`crash`, like any other frame that contradicts itself.
`OracleReport.step` holds the text. It stays out of `digest()` and out of
`oracle.jsonl`, since `step_sha256` already pins it.

**A STEP is read in a worker.** Reading the oracle's STEP is a kernel call on
the output of a hostile program, so it gets the same boundary as a program: a
**step worker**, a fresh model under a warden and its limits, that runs
`read_step` and writes the body's bytes. Those bytes then go through the body
worker (checker and measures) like a program's. Exactly one `ok` solid is a
target; zero or several solids are `runtime`, naming the count, and a
solid's refusal is `arris_refusal` with the kernel's words.

**Targets are committed.** The 300 blanked texts go into one committed file,
keyed by stem, each beside its `step_sha256`, sorted, gzip with
`mtime=0`. The re-scored table then depends on the main environment alone:
a second machine needs neither the oracle environment nor Open CASCADE. The
claim is about arris, `cq` and the reward, not about Open CASCADE.

## Consequences

- The oracle's frame grows by the STEP, far inside `MAX_RESULT_BYTES`
  (64 MiB) for a slice part; a larger one is an `overflow` `crash`. The worker always writes `step_text`; a
  frame without the field is not whole and is a `crash`.
- `step_sha256` and `oracle.jsonl` do not move: the hash covers the data
  section, as before, and the text is not in the file.
- A forged frame can still carry any STEP whose hash it computes itself
  (ADR-0004's consequence: frames are checked for consistency, not
  authenticity). It costs that program's target, and the step worker reads it
  under the same limits as any hostile input.
- The header is outside the hash, so a header edited after the blanking is
  not caught by it. Nothing reads the header for a measure.
- Comparing `step_sha256` regenerated on a second machine is left to the
  backlog: Open CASCADE across machines is not this claim.
- The committed file is CC BY 4.0 data derived from BenchCAD and keeps its
  attribution in the fixtures' README.

## Alternatives considered

- **Targets built by `cq` on arris**: a part scored against itself through
  one path proves nothing about the path, and a `cq` bug would score 1.0.
- **Regenerating the STEPs on every machine**: the claim would include Open
  CASCADE's floating point across CPUs and the oracle environment on the
  second machine, neither of which this project controls.
- **Reading the STEP in the caller's process**: the text came from a hostile
  program, and the process is the boundary (gym.md).
- **Sending the raw STEP and blanking in the caller**: the raw text differs
  on every run, so neither the frame nor any stored copy could be compared
  byte for byte.
- **Hashing the whole blanked text**: it would move every `step_sha256` and
  `oracle.jsonl`, with nothing gained, since the header carries no geometry.
