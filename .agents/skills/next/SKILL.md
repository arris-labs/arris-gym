---
name: next
description: Where things stand (cycle, plans, findings, uncommitted and unpushed work, CI, release due) and the one command to run next.
disable-model-invocation: true
---

# /next — where we are, and what to run

Read-only: it changes nothing, it orients the human. Gather in parallel:

- `AGENTS.md` "Current state" and the open cycle's section of
  `docs/ROADMAP.md` (its in-list against what landed);
- `docs/plans/*.md` but `TEMPLATE.md`: each plan's unchecked steps with
  their grades;
- `docs/ideas/*.md`: each idea's `Status` and any unanswered round;
- `docs/BACKLOG.md` §Findings: how many, and any naming the open cycle;
- `CHANGELOG.md` `## Unreleased`: whether it has bullets, and a
  `### Breaking`;
- **Release due** (`.agents/rules/git.md` §The version): a release is due
  when the open cycle is closed (its `docs/ROADMAP.md` section is compressed
  to its status line) or `## Unreleased` has bullets a consumer would see.
  `Due` names the version; there is no release workflow yet, so it says the
  release has to be planned first;
- `git status --short`, `git log --oneline origin/main..main | wc -l`
  (unpushed; no remote yet is said as such), `git describe --tags --match
  'v*' --abbrev=0` and the commits since it;
- `gh run list --branch main --limit 3` (skip it quietly if `gh` fails).

Reply in one screen, in this shape:

```
Cycle    C1, the vertical slice: 2 of 6 milestones landed
Plans    m0-sandbox: step 4 next ([2] the memory limit), 6 left
Ideas    selector-ambiguity: round 2 unanswered
Findings 1 open, on this cycle (fork: a hung reaper)
Tree     clean | 4 files staged by another session
Git      9 unpushed; no release yet; CI green
Due      push

→ /work m0-sandbox step 4-5   both [2]; tier 2 fits
  or: /idea selector-ambiguity   (one line on why it waits or wins)
```

The `→` line is one command with its arguments and a reason, and the
tier its grade gives (`.agents/tiers.md`). A step that waits on an `⚠ OPEN:`
is named as blocked, with what unblocks it. Staged or modified files you did
not make are another session's: say so, and recommend nothing that would
commit them.
