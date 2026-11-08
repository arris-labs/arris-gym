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
A program worker or body worker that ended without delivering a valid frame.
Distinct from a refusal: something died.
_Avoid_: panic

**Measures**:
What the kernel measures of a body (volume, area, centroid, bounds, counts,
genus), read by the body worker and carried on the result beside the body.

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

**Job**:
One worker's run, as the caller hands it to the zygote: its kind (a
program, a body to read back, an exec on another interpreter), its deadline and memory limit, its payload,
and the pipes its status and result come back on.
_Avoid_: request (a kernel task is a thread or process)

**Frame**:
The one JSON document a program worker or a body worker writes to its result
pipe to say how its job ended. The caller parses it and trusts none of it
beyond what costs only that program (ARCHITECTURE.md §The sandbox).

**Backstop**:
The time past a job's deadline after which the caller gives up on its status
and replaces the zygote: a bound on a zygote that stops answering, never on
a program, which its warden ends at the deadline.

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

**Mesh worker**:
The worker that tessellates a body's bytes for a picture (`dump_png`), under the
same limits as the others: the caller parses what it writes and trusts none of it.
_Avoid_: renderer

**Exec spec**:
What an exec job's worker runs once isolated: an interpreter, its arguments
and environment, and the paths it may read and execute, in place of the
zygote's (ADR-0004).

**Oracle worker**:
A program worker that, once isolated, execs the oracle environment's
interpreter on `tools/oracle/worker.py` to run one program on the oracle; it
keeps every limit of the worker it replaced (ADR-0004).
_Avoid_: oracle process, oracle sandbox

**Oracle report**:
What one program did on the oracle: an `OracleStatus`, the exception's words,
Open CASCADE's measures and the STEP hash, parsed from the oracle worker's
frame, which the caller trusts no more than any worker's. A frame that
contradicts its status or its job is a `crash`.
_Avoid_: oracle result

## Scoring

**Reward**:
The single number a result gets, by SEED.md §7.1, under a versioned config.
_Avoid_: fitness

**Score**:
What `score` returns: the reward, its terms and the field's metrics.
_Avoid_: evaluation

**Exact route**:
The IoU from the kernel's `interference` under a step budget: exact up to the
kernel's rounding, where the kernel answers (ARCHITECTURE.md §The reward,
ADR-0008).
_Avoid_: boolean IoU, analytic IoU

**Sampled route**:
The IoU estimated from seeded points classed by a winding number on each
body's mesh: what answers when the exact route refuses or spends its budget
(ADR-0008).
_Avoid_: mesh IoU, Monte Carlo IoU

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

**Unparsable**:
A program the census could not parse, kept with its exception's class and
message verbatim. A census outcome, not a status: nothing ran (ADR-0003).
_Avoid_: invalid program

**Receiver**:
What the census says a call is made on: `cq`, a root constructor
(`Workplane`), `builtin`, an imported module, or `?` when it cannot place
it. Written as the program reads, not CadQuery's runtime type (ADR-0003).

**API form**:
A call with its argument form, the kinds of its arguments:
`Workplane.extrude(num; both=bool)` (ADR-0003).
_Avoid_: signature, overload

**Subset**:
The calls and API forms `cq` implements, grown in census order; a call
outside it ends `unsupported_api` naming it (ADR-0007).
_Avoid_: coverage

**Stack**:
A `cq` `Workplane`'s objects, the ones its call made, newest last; its
result is the single solid on it (ADR-0007).

**Selector string**:
The string a program passes to `faces`, `edges` and the other selector
methods, as written: `'>Z or <Z'` (ADR-0003).

**Slice**:
The 300 BenchCAD programs C1 runs end to end: the first 100 by stem of each
of the 3 families the census ranks first among those with at least 100
programs, listed in `tests/fixtures/c1/slice.txt` (ADR-0003).
_Avoid_: sample

**Oracle**:
CadQuery on Open CASCADE, run out of process under `tools/oracle/`, never
imported.
_Avoid_: reference implementation

**Agreement tolerance**:
The four constants in `fidelity` (volume, area, centroid, bounds) inside which
`cq` on arris and the oracle measure the same part; face counts are carried,
never judged (ADR-0005).
_Avoid_: epsilon

**Fidelity**:
How far `cq` on arris agrees with the oracle on the same programs, as a table
of classified rows.
_Avoid_: compatibility

**Fidelity table**:
The fidelity rows of a corpus under their program names (`FidelityTable`),
sorted by name and counted over every row, with a digest that the order the
rows arrive in does not move. Its arris-facing cut is the **arris report**:
refusals by kind then reason, and arris bugs with their fixture.
_Avoid_: scoreboard

**Disagreement**:
One program on which `cq` on arris and the oracle differ, and which gets a
disagreement class.
_Avoid_: mismatch

**Disagreement class**:
Why a disagreement exists, one of five (`DisagreementClass`): `cq_bug`,
`arris_refusal` (with the refusal's kind), `arris_bug`, `occt_wrong` (Open
CASCADE wrong) or `by_design` (a semantic difference by design). The rule
classes what the two statuses settle; a verdict classes the rest (ADR-0006).
_Avoid_: category, bucket

**Verdict**:
A disagreement class and its one piece of evidence: a closed form, a second
oracle's record, a doc or ADR anchor (for `by_design` alone), or a
regression fixture. `compare` checks a closed form against the measures
(ADR-0006).
_Avoid_: ruling, judgement

**Fidelity row**:
One program's comparison of arris with the oracle (`FidelityRow`): `agree`,
`disagree` with its disagreement class, or `unclassified`, with both statuses,
the measure deltas and any verdict. An unclassified row makes a cycle red.
_Avoid_: fidelity result
