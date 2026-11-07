---
name: inspect
description: See a program's result without a GUI — dump it as text and PNG and look — and turn a failure into a regression fixture. Use whenever a status, a score or a fidelity row is wrong or suspicious, before trusting a green test on a change to what a program builds or scores, and when shrinking a bug.
---

# inspect — dump it and look

The human has no better view of a part than the agent: there is no GUI.
Seeing a part means writing it out and reading it. Pictures are for the
agent's eyes during work; a picture is never a test (`docs/README.md`).

## Seeing

- **Text dump**: the status, the kernel's message verbatim, the checker's
  report, volume, area, centroid, bounding box, face-kind histogram, genus,
  each reward term, and the versions. It diffs in a test.
- **PNG dump**: the body through arris's tessellation, from fixed views,
  written under `.scratch/inspect/<slug>/`, then read with the Read tool,
  which shows the image. For a disagreement, the arris and Open CASCADE
  results side by side from the same views.
- Both come from the harness: `arris_gym.dump_text(result)` and
  `arris_gym.dump_png(result, path)` (a 512 x 512 sheet: front, right, top,
  iso). Never claim to have looked at a picture that was not made.

Look for: a hole that came out faceted, a workplane on the wrong face, a
mirrored part with a matching volume, a selector that took the other of two
tied faces, a body whose volume agrees while its faces do not.

## Diagnosis loop

A failure that resists a first fix gets this before any theory:

1. **A red loop**: the smallest command that shows the failure, run in
   seconds (one test, one program).
2. **Ranked hypotheses**: three at most, each with the observation that
   would confirm or kill it. Run the cheapest discriminating one first.
3. Change one thing at a time; when a hypothesis dies, say so in the reply.

## Failure → fixture

1. Reproduce with the smallest program: drop calls while it still fails.
2. Commit it under `tests/fixtures/regression/<slug>/` (`program.py`, its
   dialect, and the expected values: status, measures, each from a closed
   form or the construction, never from arris-gym's output) with a test that
   asserts the *desired* result, marked
   `@pytest.mark.xfail(reason="<what is wrong>")`. It is strict: the fixing
   commit has to remove the mark. The fixture is never deleted. A failure
   that shows on only some runs repeats the program N times in one case, N
   the smallest count that fails on every run of the unfixed code (measured,
   in the README); otherwise a strict xfail would XPASS and flake the gate.
3. A crash or wrong result in the kernel is also a fixture candidate for
   arris: report it in `../arris/docs/ideas/`, never fix it from here.

A finding a run measured but nobody shrank yet goes to `docs/BACKLOG.md`
§Findings first, with its corpus revision, program id and commit.
