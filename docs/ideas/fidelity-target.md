# Idea: fidelity-target

- Status: Open
- Raised: 2026-11-10
- Prompt (verbatim from the human): "/idea fidelity-target"

## Problem

C2 cannot finish without a fidelity target: its acceptance is "0 unclassified
on both corpora; the fidelity target met" (`docs/ROADMAP.md` §C2), and SEED.md
§9.8 lists the target as an `⚠ OPEN` to close by ADR "after the cycle 1
measurement". The roadmap orders it first, before the subset grows, so the
growth has something to aim at and cannot pick its own finish line.

The C1 number does not extrapolate. On the slice (`tests/fixtures/c1/fidelity.json`)
200 of 300 agree and 100 are `arris_bug`: every one of them the
`union-coplanar-third-operand` finding, one arris defect on one family. `cq_bug`,
`by_design` and `occt_wrong` are 0. The slice was chosen as the 3 families of
106 that need the *least* of CadQuery (ADR-0003). So 67% says almost nothing
about BenchCAD's 17,900 programs, and nothing about CAD-Recode. The C1 subset
holds 13 API forms. On the full corpus, most programs would end
`unsupported_api`, which ADR-0006 classes `cq_bug`.

The target has to answer three things: **what** is counted, **over which
programs**, and **how much**. Only the last needs a measurement. The first two
can be decided now.

## Constraints it runs into

- **SEED.md §9.8 / §6 C2**: the target is set by ADR. The decision point is that
  low fidelity from arris refusals ranks arris's next cycle, and low fidelity
  from CadQuery semantics narrows the subset. Either way, the target must say
  whose failure a row is.
- **gym.md, "Failures are counted"**: the denominator is all programs. A figure
  over a part of the corpus is reported only beside the all-programs one, and is
  labelled as such.
- **ADR-0006**: `unsupported_api` against an oracle `ok` is `cq_bug`, and an
  intended refusal is re-classed `by_design` with an anchor. Any target that
  treats out-of-subset programs differently is a view over the rows. It must
  not change the classes.
- **ADR-0005**: the agreement tolerance is fixed. A target never loosens it.
- **arris is not edited from here** (AGENTS.md). Any target that arris rows can
  fail would make C2's close depend on arris's release schedule.
- **Cost**: the oracle pays ~1.5 s of start-up per program (backlog line on an
  oracle zygote). 17,900 programs are ~7.5 CPU-hours, so a few hours on a
  workstation. `fidelity.json` is 189 KB for 300 rows, about 11 MB for BenchCAD.
- **GLOSSARY.md**: *coverage* is under *Subset*'s _Avoid_. Any new term must
  not bring it back (see §The words).

## Options

### A — One agreement rate per corpus
Target: `agree / all programs ≥ T` on each corpus. It is the number a reader
expects and the one SEED's "fidelity published" promises.
- For: simple. Matches what gets published. The denominator rule holds by
  construction.
- Against: it mixes three owners. Arris rows (arris's to fix), out-of-subset
  programs (a scope choice) and real `cq` bugs all lower the same number. The
  C2 close would wait on arris bumps. The decision point needs the number taken
  apart anyway. A 100-program arris bug moves T as much as 100 `cq` bugs do.
- Cost: ADR + baseline run, ~4 steps.

### B — Agreement with arris rows excused
Target: `(agree + arris_refusal + arris_bug + occt_wrong) / all ≥ T`. That is
the fraction where `cq` is not at fault.
- For: arris-gym controls everything the target counts. The C2 close does not
  wait on arris.
- Against: out-of-subset programs still count as faults, so T is mostly a
  scope number in disguise. Nothing separates "the subset is wrong" from "the
  subset is small". A wrong `cq` result and a missing form weigh the same,
  although the first is a correctness bug and the second is a roadmap item.
- Cost: as A.

### C — Reach, and no `cq` bug inside the subset (two numbers)
Split the question the way the decision point does:
1. **Reach** ≥ T: the share of each corpus's programs whose every API form
   (by the census, statically) lies in the subset. It is a scope number. It
   grows step by step in census order, and the census can plot it ahead of any
   run: "with the next k forms, reach is r(k)". All programs are the
   denominator.
2. **In-subset correctness = 0 `cq_bug`**: every in-subset program agrees, or is
   an arris, `occt_wrong` or `by_design` row. It is an invariant, not a
   percentage. A `cq_bug` inside the subset is either fixed, or the subset is
   narrowed and the row re-classed `by_design` with its anchor. That is the
   decision point's "the subset narrows", made mechanical.

The fidelity table still publishes plain agreement over all programs (A's
number) beside them, with arris's rows as the arris report.
- For: each number has one owner and one lever. The target T is chosen from a
  curve before any growth, not from a run. A wrong `cq` answer can never be
  averaged away. Arris rows rank arris's cycle and do not block C2.
- Against: a second number to explain. "Reach" is a static claim, and a program
  whose forms are all in the subset can still fail on context (the backlog's
  "`cq` keeps no CadQuery context along a chain"). C2 must handle those or
  narrow the subset, which is the point, but it can be work. The census needs a
  per-program form set and a reach curve, which is new code in `census`.
- Cost: ADR, the reach curve in `census`, a full-corpus fidelity command
  (`tools/cq_slice.py` generalised) and the baseline run, ~5–6 steps. The
  CAD-Recode pin and its census are already in C2's in-list.

### D — A pinned sample instead of the full corpora
Orthogonal to A–C: measure on a seeded, per-family sample (say 50 per family,
~5,300 programs) instead of all 17,900 plus CAD-Recode's split.
- For: about a third of the oracle time.
- Against: the target becomes a claim about a sample, while every other number
  the gym publishes is over a whole pinned corpus. Rare forms are where `cq`
  bugs hide. The oracle zygote (backlog) makes the full run cheap enough anyway.

### Do nothing
C2 closes on "0 unclassified" alone. This goes against SEED.md §9.8, a kickoff
decision that is not re-litigated, and leaves the subset's growth with no
finish line.

## Recommendation

**C over the full corpora (not D)**, each corpus with its own target and
nothing pooled, so BenchCAD's size cannot swamp CAD-Recode.

A and B lose because each folds two or three owners into one number. The
decision point needs them apart, and C does that by construction. A's number is
still published, so nothing a reader expects goes missing.

T itself is set in a second round, once the census's reach curve over both
corpora is measured. The curve shows where each next form stops paying (the
knee), and that is the honest place to set T. The slice's 200/300 does not show
it.

I would change my mind if the reach curve proves flat: if no small set of forms
reaches a meaningful share, then the subset's growth is the wrong lever, and A
over a narrowed C2 scope would be simpler.

## The words

- *Fidelity target* (new): "The numbers C2 must meet on each corpus: a reach of
  at least T and no `cq_bug` among in-subset programs (ADR-00xx). Plain
  agreement over all programs is published beside it, never targeted."
- *In-subset program* (new): "A corpus program whose every API form the census
  counts lies in the subset; decided statically, never by running it."
- *Reach* (new): "The share of a corpus's programs that are in-subset, over all
  its programs." It is chosen over *coverage*, which `GLOSSARY.md` lists under
  *Subset*'s _Avoid_. *Reach* is a property of a corpus against the subset, not
  of the subset alone.

## Decision for the human

Round 1:

❓ **Q1 — What the target counts**: (A) one agreement rate, (B) agreement with
arris rows excused, or (C) reach ≥ T plus 0 `cq_bug` among in-subset programs,
with plain agreement published beside them.
➡️ C: one owner per number, and the decision point becomes mechanical.

❓ **Q2 — Over which programs**: (A) the full corpora, BenchCAD `code_gen` and the
CAD-Recode validation split, each with its own target, or (B) a pinned per-family
sample, or (C) both pooled.
➡️ A: every other gym number is over a whole pinned corpus, and the oracle
zygote makes the cost bearable.

❓ **Q3 — When T is set**: (A) after the census's reach curve over both corpora
is measured, in the same ADR, or (B) now, from the slice.
➡️ A: the slice is the 3 easiest families and cannot locate the knee.

❓ **Q4 — An ADR**: one ADR, written by the plan, closes SEED.md §9.8's `⚠ OPEN`
and amends `docs/ROADMAP.md` §C2's "from that number" to "from the reach curve
over both corpora".
➡️ Yes: a kickoff `⚠ OPEN` closes only by ADR.

*Later* (they wait on Q1–Q3):
- the value of T per corpus, read from the measured reach curves;
- whether an in-subset `by_design` row needs a budget, so the subset cannot
  meet "0 `cq_bug`" by narrowing itself to nothing;
- whether the oracle zygote comes before the baseline run, or the first run
  just pays the 7.5 hours.

## Decision

(empty)
