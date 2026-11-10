# Git: trunk-based, always green

- **Every commit** passes `.githooks/pre-commit`; never `--no-verify`. The
  hook runs `tools/gate.sh` unless the commit stages prose only (`*.md`,
  `.agents/`, `docs/`): the layer and fixture checks, the generated API
  reference, ruff, `mypy --strict` and pytest. When the gate passes a minute,
  it is split by an ADR, not by skipping stages.
- **No foreground waits.** A run expected to take over a minute, and a CI
  watch, runs with `run_in_background`, and the agent goes on with what
  does not depend on its result. A foreground `until`, `while` or `sleep`
  loop, or a `tail --pid`/`tail -f`, waiting on one is never written: the
  completion notification is the wait. In Claude Code `tools/bash-guard.sh`
  refuses it (a PreToolUse hook).
- Commit **directly to `main`**, one plan step per commit. Branch
  (`plan/<slug>`, rebased, `merge --ff-only`, deleted after) only when a
  plan may be thrown away or the human asked to review first.
- Never rewrite `main` (no amend of a pushed commit, no force-push, no
  rebase). Never push unless asked.
- Stage deliberately: read `git status` and `git diff`, no blind `git add
  -A`. No `git stash`: a pop can bring back another session's work
  (`tools/bash-guard.sh` refuses it). A changed fixture expectation
  (`tests/fixtures/**`) is staged only with an intentional change of
  behaviour, and the message says `fixtures:` and why.
- **`uv.lock` is committed** and changes only in a commit that means to
  change a dependency. A bump of `arris` or `numpy` is its own plan: it can
  move results, so it re-runs the fidelity table.

## Message format

```
type(scope): imperative summary, lower case, no period  (plans/<slug> step N)

Why, not what. Cite the ADRs and docs that justify it or that it updated.
Name any public type or signature it changes.
```

- `type`: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`,
  `build`, `ci`, `fixtures`. `scope`: module names (`sandbox`, `cq`, `reward`,
  `census`, `fidelity`, `rescore`, several as `sandbox,cq`) or `docs`, `plan`,
  `adr`, `tools`, `oracle`.
- The `(plans/<slug> step N)` suffix marks every plan-step commit;
  retirement is `docs: retire plan <slug>`.
- **Attribution**: a commit that repairs an earlier step's work carries
  that step's suffix, never a later one's, a fix found by the retirement
  review included; `(plans/<slug> review)` is only for a fix that belongs
  to no single step.
- Docs change in the **same commit** as the behaviour; a docs-only catch-up
  is `docs(sync): …`.
- No `Co-Authored-By` or tool trailers.

## Tags and publishing

- Creating the remote, reserving `arris-gym` on PyPI (a trusted publisher
  for `release.yml`, environment `pypi`) and every release are the human's
  acts. `/release` prepares the commits; the **human tags and pushes** and
  approves the `pypi` reviewer; an agent never tags, pushes, approves or
  uploads. `release.yml` publishes only from a `v*` tag.

### The version

- `main` carries the next version with `.dev0` in `pyproject.toml`
  (`0.N.0.dev0`), the only place it is written besides `CHANGELOG.md`'s
  headings: no doc or README states it.
- Pre-1.0, `0.y.z` is `y` breaking. **Closing a cycle bumps the minor**;
  **a release between cycles bumps the patch**, unless `CHANGELOG.md`'s
  `Unreleased` has a `### Breaking` bullet.

### The changelog

`CHANGELOG.md` is what a consumer reads.

- An entry is written in the commit that makes the change; a plan's
  bullets by its `/retire-plan` commit. Changes no consumer can see
  (process, tooling, tests, docs) write nothing.
- Bullets go under `## Unreleased`, for a reader who has read only
  `README.md`: what they can now do, the statuses they will see, no ADR
  numbers, plan slugs or fixture names. A changed public type or signature
  goes under `### Breaking` with its one-line fix, in the same commit. A
  change that moves a reward says so and names the new reward version.

## Without asking

While executing a plan: run checks, commit each step, tick boxes, edit the
plan. Branching, tagging, pushing, resetting, rewriting and publishing are
asked first.
