# arris-gym docs

`ARCHITECTURE.md` and `ROADMAP.md` are the living design; ADRs record
decisions and their reasons at the moment they were taken and are never
edited after acceptance (supersede with a new one). `BENCHMARK-SURVEY.md` is
the survey of the field. `SEED.md` at the repo root is the charter: problem,
competition, differentiators, chosen stack, the decisions taken at kickoff.

| Doc | What it holds |
|---|---|
| [architecture](ARCHITECTURE.md) | Modules and the layer rule, `ExecResult` and the status model, the sandbox's process, timeout and memory model, the dialect boundary, the reward and its versioning, determinism rules, the oracle |
| [roadmap](ROADMAP.md) | Cycles with acceptance as numbers; the named cycles not yet opened |
| [benchmark survey](BENCHMARK-SURVEY.md) | The benchmarks, models and RL work surveyed, with sources; most numbers unverified |
| [arris API](ARRIS_API.md) | Generated from the pinned wheel's stubs: what arris offers, never edited by hand |
| [adr/](adr/README.md) | Architecture decision records |
| [glossary](../GLOSSARY.md) | The project's words, one meaning each, and the synonyms they replace |
| [review](../.agents/review.md) | What the review of a plan's diff checks, read by the reviewer at `/retire-plan` |

Conventions used in these docs: `⚠ OPEN:` marks a question deliberately
left for implementation time; a decision that closes it gets an ADR.

## Document lifecycle

Three tiers, three lifetimes. Which tier a sentence belongs to is decided
by how long it should stay true.

| Tier | Files | Lifetime | Rule |
|---|---|---|---|
| Charter + decisions | `SEED.md`, `adr/` | Append-only | `SEED.md` is frozen at kickoff. A change of mind is a new ADR that supersedes an old one; the old one is never edited. |
| Design | `ARCHITECTURE.md`, `ROADMAP.md` | Living | Present tense; describes the system as it is *now*. The commit that changes behaviour updates the doc. No "as of M2" prose — git blame is the history. Milestone progress is one status line per milestone in `ROADMAP.md`, nothing more. |
| Ideas | `ideas/<slug>.md` | Until decided | A **brainstorm**, not a todo: problem, options with trade-offs, cost, conflicts, recommendation, the decision for the human. From `ideas/TEMPLATE.md`. Accepted → absorbed by its plan and deleted (a plan covering only part of it cuts the file down to the rest); rejected → one line under "Rejected" in `BACKLOG.md` with the reason, file deleted; parked → kept with `Status: Parked`. |
| Finding | `BACKLOG.md` §Findings | Until fixed | A defect a corpus run, a property test or CI **measured**: what, where, the run, commit and seed, how to replay it, its state. Written down the moment it is seen. Reconciled at every `/close-cycle`. |
| Changelog | `../CHANGELOG.md` | Append-only per release | What a consumer can now do, the statuses they will see, and each break with its fix. Written under `Unreleased` by the commit that makes the change. |
| Plans | `plans/<slug>.md` | Ephemeral | Created from `plans/TEMPLATE.md` when an idea is picked up; executed with checkboxes ticked and commits referencing it; on completion its commits are reviewed against it, the durable parts move to tier 1/2 and **the plan is deleted**. Deletion is the "done" signal; git keeps it. At most two plans active, each under ~150 lines and ~10 steps; larger work is milestone plans. |

Raw ideas go in `BACKLOG.md`, one line each. A line that needs thinking
becomes an idea; one that is obvious goes straight to a plan; not every
idea becomes a plan. The pipeline is walked by the shared skills `/idea`,
`/plan`, `/work`, `/retire-plan` and, at a cycle boundary, `/close-cycle`
(`.agents/skills/`, symlinked into `.claude/skills/`), under the rules in
`.agents/rules/`. `inspect`, beside them, is how the agent sees a part it
is changing without a GUI. For the human: `/next` says where things stand
and what to run, `/handoff` writes a note a fresh session continues from,
and `/retro` mines a plan's sessions for improvements to this environment.

`AGENTS.md`'s "Current state" is capped at ~15 lines and speaks at
milestone granularity only.

**Drift review** at every cycle boundary: the agent reads each design doc
against the code and lists discrepancies; the cycle is not done until the
list is empty. It is step 3 of `/close-cycle`.

A finished cycle **compresses in place**: `ROADMAP.md` keeps one section
per cycle — goal, status line, in/out/accept — and the next cycle is
appended below it. There is never a second roadmap file.

## What is different from an application's docs

arris-gym is a library others score with, so four things an application's
process leaves implicit are written down here:

- **Acceptance is a number, never a picture.** A milestone closes on a run:
  statuses, measures, rewards, fidelity rows, digests equal on two machines.
  `inspect` renders PNGs for the *agent's* eyes during work; no picture is
  ever a test.
- **The public API is a design doc.** A change to a public type or
  signature is a design delta in the plan, and a docstring on every public
  item is part of the step. Pre-1.0, breaking changes are allowed but named
  in the commit body and the changelog.
- **Every failure becomes a fixture.** A reproduced bug is shrunk to a
  minimal program and committed with the desired assertion before it is
  fixed (`.agents/rules/gym.md`).
- **A score is a claim others will cite.** A change that can move one bumps
  the reward's version; a number published outside this repository is one
  anyone can regenerate.
