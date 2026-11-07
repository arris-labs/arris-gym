# arris-gym glossary

The words this project uses for its own concepts, one meaning each. A term
here is used as written in code, docs, plans and commits; the words under
_Avoid_ are the synonyms it replaces. Definitions say what a thing **is**;
how it works lives in the design doc named beside it. Standard CAD and RL
vocabulary (B-Rep, IoU, Chamfer distance, GRPO) means what the literature
means; arris's own terms mean what `../arris/GLOSSARY.md` says.

## Programs and outcomes

**Program**:
The text of one CAD script, in one dialect, as a model or a corpus wrote it.
Hostile input until proven otherwise (ARCHITECTURE.md §The sandbox).
_Avoid_: script, snippet, code sample

**Dialect**:
The API a program is written against: `arris` (`arris.build`) or `cq` (the
CadQuery subset).
_Avoid_: language, backend, frontend

**Status**:
The typed outcome of running a program, one of eight (ARCHITECTURE.md
§Outcomes). Every program has exactly one.
_Avoid_: result code

**Refusal**:
The kernel declining an operation with a typed `ArrisError`: status
`arris_refusal`, its **kind** the exception's class name. An answer, not a
crash.
_Avoid_: kernel error

**Crash**:
A program worker that ended without delivering a result. Distinct from a
refusal: something died.
_Avoid_: panic

**Failure**:
Any status but `ok`. Failures are counted in every aggregate. An error is
something else: a Python exception.

**Target**:
The body a result is scored against.
_Avoid_: gold

## The sandbox

**Sandbox**:
The whole of what runs a program in isolation: the zygote, and the wardens,
program workers and body workers it forks (ADR-0002).
_Avoid_: jail

**Zygote**:
The clean interpreter that imports everything, builds nothing and forks a
program worker per program (ADR-0001).
_Avoid_: master

**Warden**:
The process between the zygote and one worker: it enters the worker's
namespaces, owns its deadline and reports how it ended (ADR-0002).
_Avoid_: supervisor, monitor

**Program worker**:
The process forked for one program, ended with it (ADR-0001); PID 1 of its
own namespaces (ADR-0002).
_Avoid_: runner, executor

**Body worker**:
The worker that reads a program worker's body bytes back, checks and measures
them, under the same limits: nothing a program delivers is trusted (ADR-0002).
_Avoid_: verifier

## Scoring

**Reward**:
The single number a result gets, by SEED.md §7.1, under a versioned config.
_Avoid_: fitness

**Score**:
What `score` returns: the reward, its terms and the field's metrics.
_Avoid_: evaluation

**Field metric**:
A metric computed the way a published benchmark defines it, so its numbers
compare with theirs. Kept apart from ours.
_Avoid_: baseline metric

**Digest**:
The SHA-256 of a body's bytes, or of a report's rows without anything
wall-clock. Equal digests are what determinism means here.
_Avoid_: checksum, fingerprint

## Corpora and fidelity

**Corpus**:
A pinned set of programs from one source, with its licence.
_Avoid_: dataset (a dataset is what a host publishes)

**Census**:
The count of every API call, selector string and argument form in a corpus.
It decides what `cq` implements and in what order.
_Avoid_: audit

**Oracle**:
CadQuery on Open CASCADE, run out of process under `tools/oracle/`, never
imported.
_Avoid_: reference implementation

**Fidelity**:
How far `cq` on arris agrees with the oracle on the same programs, as a table
of classified rows.
_Avoid_: compatibility

**Disagreement**:
One program on which `cq` on arris and the oracle differ, and which gets a
class: `cq` bug, arris refusal, arris bug, Open CASCADE wrong, or semantic
difference by design.
_Avoid_: mismatch
