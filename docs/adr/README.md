# Architecture decision records

One file per decision, numbered `NNNN-<slug>.md`, never edited after
acceptance — a change of mind is a new ADR that supersedes the old one.
Format: Context, Decision, Consequences, Alternatives considered. An ADR
whose design was informed by CadQuery's source names the file or module read,
so provenance is auditable (`PROVENANCE.md`, SEED.md §8).

The decisions taken at kickoff live in `SEED.md` §9 and are not repeated
here; the first ADR is the first decision taken *after* the seed. Open at
kickoff, each closed by an ADR (SEED.md §10.8): the C2 fidelity target;
mesh-based vs. exact IoU as the default until `classify_points` lands; the
reward weights and τ; how CadQuery's string selectors map onto arris's
selection when they are ambiguous on curved faces; whether B-Rep descriptions
for the own benchmark are exact or quantised; which open base model the
training cycle starts from.

| # | Title | Status |
|---|---|---|
| [0001](0001-a-program-runs-on-a-fresh-model-in-a-forked-process.md) | A program runs on a fresh model in a forked process | accepted |
