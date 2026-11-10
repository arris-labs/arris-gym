---
name: release
description: Walk a release: drop .dev0 and cut the changelog heading, reopen main at the next .dev0, the human tags and pushes once, then watch release.yml and its reviewed PyPI publish.
disable-model-invocation: true
argument-hint: <version, e.g. 0.1.0 — pyproject's version without .dev0>
---

# /release — one tag, one reviewed publish

Publishing is `.github/workflows/release.yml`, run from a `vX.Y.Z` tag the
human pushes (`.agents/rules/git.md` §Tags and publishing). Its `publish-pypi`
job waits in the GitHub environment `pypi`, which has a required reviewer and
a PyPI trusted publisher. This skill prepares the commits, then waits for the
human at the tag and at the reviewer. It never tags, pushes, approves a
publish, or publishes by hand.

## Do

1. **Check the ground.** On `main`, a clean tree, `main` equal to its
   upstream (`git status`, `git rev-list --count @{u}..main`), and the last
   `ci.yml` run on `main` green (`gh run list --branch main`; CI takes
   ~40 min, so a commit not yet run is waited for, in the background). Check
   that the `pypi` environment has a required reviewer
   (`gh api repos/{owner}/{repo}/environments`); without it, stop and say so.
   Start `tools/gate.sh` with `run_in_background` and go on.
2. **Pick the version.** The argument, else `pyproject.toml`'s version minus
   `.dev0`. It must match the bump `.agents/rules/git.md` §The version gives:
   a closed cycle bumps the minor; a release between cycles bumps the patch,
   or the minor when `## Unreleased` has a `### Breaking` bullet. Any
   mismatch: stop and ask.
3. **Prepare the release commit:**
   - `pyproject.toml`: `version` becomes `X.Y.Z`; `uv lock` and confirm
     `uv.lock` changed only in arris-gym's own version.
   - `CHANGELOG.md`: `## Unreleased` keeps its bullets under a new
     `## X.Y.Z — <YYYY-MM-DD>` heading, with an empty `## Unreleased` above.
   - `AGENTS.md` "Current state": say the release made (`X.Y.Z published`
     once it is; until then `X.Y.Z tagged`).
   - **Packaging proof** (a local rehearsal; the tag's CI run is the gate):
     in a scratch directory, `uv build --out-dir <scratch>/dist`,
     `uvx twine check --strict <scratch>/dist/*`, and the wheel installed
     into a clean venv, `python -I -c "import arris_gym"`. A failure stops
     the release before the tag.
   - `tools/release-check.sh vX.Y.Z` and `tools/release-check-test.sh` pass.
   - Commit `chore(release): X.Y.Z`, the body saying this is the commit
     `release.yml` publishes from the tag. Stage by name, never `git add -A`.
4. **Reopen `main`** so one push carries both commits: `pyproject.toml` to
   the next `.dev0` (`X.(Y+1).0.dev0` when this release closed a cycle, else
   `X.Y.(Z+1).dev0`), `uv lock`, commit `chore(release): reopen main at
   <version>.dev0`. Tagging it by mistake is safe: `release-check.sh`
   refuses a `.dev0` version.
5. **The human tags and pushes.** Stop and say exactly, the tag on the
   release commit, not on `main`:
   `git tag vX.Y.Z <release-commit> && git push origin main vX.Y.Z`.
   Wait for the human's word that it is pushed. Never push or tag.
6. **Watch the run.** `gh run list --workflow release.yml --limit 3`, then
   `gh run watch <id>` with `run_in_background`; also find the tag's own
   `ci.yml` run. Say up front that the `pypi` approval is asked once
   `release-check` and `build` finish, and the human approves only after the
   tag's `ci.yml` run is green; an early approval fails safe and its rerun
   is the human's to ask for. A failed job stops here: report it with its
   log link; a publish is never rerun without the human's word. If `gh`
   fails, stop and say so.
7. **Reply.** The release commit, the reopening commit, the tag the human
   pushed, each job's result, anything surprising, and the reviewer the
   human still owes if any.

`$ARGUMENTS`
