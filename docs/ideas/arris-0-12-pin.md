# Idea: arris-0-12-pin

- Status: Open
- Raised: 2026-11-24
- Prompt (verbatim from the human): "arris just released v0.12.0 - should we migrate to it?"

## Problem

The 0.11.1 pin supplies the C2 baseline of 14,150/17,900 BenchCAD programs
in reach and 968/968 CAD-Recode programs in reach. The 0.12.0 changelog
explicitly names chained cylinder fuses on a shared end plane. That matches
the construction in `regression/cq-union-three-coplanar-cylinders`, which
backs 100 BenchCAD verdicts. The torus–box point-contact fix also matches a
reported refusal in [the backlog](../BACKLOG.md). Both are candidates for
verification against the published wheel. The release also changes revolve
behavior and some blend refusals, so expected improvements can come with
other status, topology, or reward changes.
[Kernel changelog](https://github.com/arris-labs/arris/blob/v0.12.0/CHANGELOG.md)

## Constraints it runs into

SEED.md and `.agents/rules/git.md` require an exact pin and a dedicated plan
that reruns fidelity. ADR-0021 names the bump through `versions.arris` and
keeps the reward version for changes to arris-gym's scoring. A table digest
can move through version metadata alone. Check row-level deltas on both
corpora, rescore the C1 slice, and compare the new rescore digest across
x86-64 and aarch64. Published Linux wheels exist for both architectures.
[PyPI release metadata](https://pypi.org/pypi/arris/0.12.0/json)

The glossary's *reach* counts programs inside the declared subset. Kernel
fixes may raise agreement at the same reach. The lofts and tapers lift still
owns the subset expansion under ADR-0012 and ADR-0014. No new glossary term
is needed. Adopting batch point classification or tight bounds would
introduce a separate scoring or geometry change and warrants its own
evaluation.

## Options

### A — Establish a 0.12.0 baseline before lofts and tapers

Budget roughly five to seven plan steps, based on the previous bump.
Refresh the pin and generated API reference, then use the regression
fixtures and corpus tables to attribute changed rows. Recheck the C1
fidelity and rescore evidence. This delays the subset lift by one plan
and gives that lift a measured kernel baseline for boolean results.

### B — Lift lofts and tapers first, then bump

Deliver the next roadmap item on its existing baseline and pay roughly
the same migration cost afterward, with a larger subset to reverify.
The release notes establish no new loft or taper API prerequisite.
This order makes sense if immediate subset reach has priority over
resolving the current fidelity findings.

### Keep 0.11.1 for C2

Avoid the migration work this cycle and preserve the current comparison
baseline. Carry known kernel refusals into the next plans and postpone
checking whether 0.12.0 resolves them.

## Recommendation

Choose A. The shared-end-plane fix targets a known failure family and
gives the bump a concrete acceptance case. Keep 0.11.1 if the wheel does
not reproduce the expected fix and the broader comparison shows no
material gain, or if the migration exposes unresolved regressions.
The impact on the corpus and rewards remains unmeasured.

## Decision for the human

❓ **Q1 — Upgrade order.** Should we plan the standalone 0.12.0 bump before
`lift-lofts-and-tapers` (A), lift first (B), or keep 0.11.1 for C2 (C)?

➡️ A. Measure the kernel changes on the current subset before expanding it.

ADR-0021 already covers the versioning decision. No new ADR is proposed.

## Decision
