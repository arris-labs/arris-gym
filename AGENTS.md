# arris-gym

A Python library that runs model-written CAD programs on the `arris` B-Rep
kernel in a sandbox, returns a typed outcome for every program, and scores the
result against a target: exact, deterministic, every failure counted. It speaks
`arris.build` and a CadQuery-compatible subset. Benchmark harnesses and RL
training loops are built on top of it. It belongs to the `arris-labs` family and
depends on the `arris` wheel only.

Read in this order: `SEED.md` (charter, competition, stack, the decisions
taken at kickoff), `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/adr/`, then
the rules in `.agents/rules/*.md` (git, docs lifecycle, gym) — Claude Code
loads them automatically via `.claude/rules`; any other agent reads them here.
`docs/ARRIS_API.md` is what the pinned wheel offers. `GLOSSARY.md` holds the
project's words, one meaning each: use them as written. Skills live in
`.agents/skills/` (same symlink arrangement): the idea → plan → work →
retire → close-cycle pipeline, `inspect` for seeing a part, and for the
human `/next`, `/handoff` and `/retro`.

## Setup (once per clone)

```sh
git config core.hooksPath .githooks   # the gate (tools/gate.sh) before every commit that touches code
uv sync                               # the locked environment, Python 3.12
```

## Current state

**C1 closed** (2026-11-10): the vertical slice runs end to end. `run`,
`run_many` and `Sandbox` execute programs in a warden-supervised, namespaced,
Landlocked worker (ADR-0001, ADR-0002); `arris-gym census` fixed the 300-program
slice (ADR-0003); CadQuery runs in an oracle worker and `fidelity` classes each
pair (ADR-0004 to ADR-0006); `dialect="cq"` runs the census's 13 API forms, 200
of the 300 slice programs agreeing with the oracle, 100 an arris bug, 0
unclassified (ADR-0007); `score` returns a frozen `Score`, reward version 1
(ADR-0008 to ADR-0010); `arris-gym rescore benchcad` re-scores the slice
against the oracle's STEPs, its digest equal on x86-64 and aarch64 (ADR-0011).
**0.1.0 published** (2026-11-10).
**C2 target set** (2026-11-12): ADR-0014 fixes the fidelity target, a reach of
85% on BenchCAD and 100% on CAD-Recode with no in-subset `cq_bug`; the
baseline is reach 10.5% and 717 in-subset `cq_bug` rows on BenchCAD, 0 on
CAD-Recode (neither worker read its `r = …` end form at that baseline).
**Next:** C2's growth: lift end forms, forms and selectors in reach-curve order
(`docs/ROADMAP.md`).

## Rules that are not derivable from the code

- `run` never raises on a program; every program gets a status, every
  aggregate counts every failure, and the kernel's words stay verbatim.
  Same program, same bits on every machine. Details: `.agents/rules/gym.md`.
- A program is hostile input: it runs only in a program worker, on a fresh
  model (ADR-0001). The process is the boundary.
- `sandbox`, `reward` and `cq` never import `train`, `rescore` or `tools/`;
  `cq` imports only `arris`. CadQuery and OCP live only in `tools/oracle/`, run
  and never imported; `cq` never moves into the `arris` repository.
- Every failure becomes a fixture; acceptance is numbers (statuses, measures,
  rewards, fidelity rows, digests), never a picture. The agent looks at a part
  itself with the `inspect` skill; the human has no better view of it.
- Decisions go in `docs/adr/`; `⚠ OPEN:` in a doc marks a deferred one.
  Kickoff decisions are in `SEED.md` §9 and are not re-litigated.
- Update this file's "Current state" when a milestone lands; keep it under
  ~15 lines — the roadmap holds the detail.
- Backlog line → `/idea` (brainstorm, `docs/ideas/`) → `/plan` (todo,
  `docs/plans/`) → `/work` (one step, one commit) → `/retire-plan` (the
  diff reviewed against the plan, docs updated, plan deleted);
  `/close-cycle` at a roadmap boundary. Not every idea becomes a plan.
  Details: `.agents/rules/docs-lifecycle.md`.
- `/work <slug>` with no step **conducts** the plan: each step a fresh
  subagent on its tier (`.agents/tiers.md` maps tiers to models), then the
  conducting session runs `/retire-plan`. Waits (gate, CI) run in the
  background, never in a foreground loop.
- Trunk-based git, `main` always green, commit per plan step, never push
  or publish unasked: `.agents/rules/git.md`. `main` carries the next
  version with `.dev0`. A change a consumer would notice writes its
  `CHANGELOG.md` bullet under `Unreleased` in the same commit.
- arris asks go to `../arris/docs/ideas/`; no arris code is edited from here.
  Do not read `../arrix` for anything in this project.
