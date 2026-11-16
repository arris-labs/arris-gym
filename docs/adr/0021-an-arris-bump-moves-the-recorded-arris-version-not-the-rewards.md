# ADR-0021: An arris bump moves the recorded arris version, not the reward's

- Status: accepted
- Date: 2026-11-16

## Context

This is the first bump of `arris` since the slice (0.10.0 to 0.11.1,
plans/bump-arris-0-11). gym.md says "a change that can move any reward,
however slightly, bumps the version". A kernel release can move a reward:
0.11.0 changes the face quadrature, the `Coincident` verdict between curves,
the tolerances of a moved STEP body, and which fillets build. Read literally,
the rule bumps `RewardConfig`'s version on every arris release.

What a row already holds:

- Every result row records `versions.arris`, `versions.numpy` and the reward's
  version (SEED.md §9).
- `Score.digest()` and the table digest hash all three (ADR-0011's amendment).
- The cache key holds the arris version (SEED.md, the sandbox's result cache).

So a kernel bump already moves every digest and every cache key, through the
arris version string.

## Decision

**The reward's version names the reward's meaning:** `RewardConfig`'s weights,
τ and N, the formula, and arris-gym's code on the score's path. A change to any
of these bumps it (ADR-0008, ADR-0009).

**A kernel bump is named by `versions.arris` alone.** A bump of `arris` (or of
`numpy`) does not bump the reward's version. Its own plan re-runs the tables
(SEED.md §9, git.md), and the rows that moved are traced to the kernel's
changelog in that plan's commits.

A reward is therefore reproduced by the triple (arris, numpy, reward version),
never by the reward's version alone. A report that compares rewards across
rows with different `versions.arris` says so.

## Consequences

- The reward's version moves only when arris-gym changes what it computes, so
  a reader can tell a formula change from a kernel change.
- gym.md and `docs/ARCHITECTURE.md` §The reward say that a pin bump is named
  by the pinned version.
- A training run that mixes rows of two arris versions mixes two kernels under
  one reward version. The rows' `versions.arris` is what tells them apart.

## Alternatives considered

- **Bump the reward's version on every kernel bump.** It is the literal
  rule, but it would make the reward's version a second copy of
  `versions.arris`. It would also hide formula changes among kernel releases.
- **Fold the arris version into the reward's version** (`1+arris0.11.1`). It
  duplicates the row's own field, and every consumer would have to parse it.
