# ADR-0009: The surface term is a seeded nearest-sample distance, under a τ five times its noise floor

- Status: accepted
- Date: 2026-11-09

## Context

SEED.md §7.1 gives the reward four terms beside the IoU's 0.6: `surface`
(0.15), a symmetric Chamfer distance through exp(−d/τ); `measures` (0.15);
`topology` (0.10). It leaves τ, the sample count and the exact formulas
open, and `docs/ARCHITECTURE.md` §Determinism forbids the platform's `exp`
on a score's path. plans/m4-reward fixed the formulas' shape; this ADR
records them, with τ and the surface's sample count measured.

A Chamfer distance between two point samplings is never 0 for two
samplings that differ, even of one surface: each sample's nearest sample on
the other side sits about half a sample spacing away. That is the term's
**noise floor**, and a part built two ways (another triangulation, the same
solid) meets it, since its mesh draws other samples. τ has to sit well above
it, or the term punishes a correct part for its samples.

`tools/reward_calibrate.py surface` measured it on the C1 slice's 200 `ok`
bodies (100 `phone_stand`, 100 `venturi_tube`; BenchCAD `code_gen` at
`5919f578`, CC BY 4.0) on arris 0.10.0, each meshed at ADR-0008's chord of
1/200 of its diagonal. The floor is d between one body's mesh sampled from
two seeds; the ladder is d between the body as target and the candidates
ADR-0008 built (moved by 0.01–0.3 of its diagonal, turned 2°–20°, the next
body of its family), every body counted. d is over the target's diagonal.
Seconds are wall-clock per d with 30 processes at once, for the reader only.

| Samples per body | floor min | median | max | median s per d |
|---|---|---|---|---|
| 2,662 | 0.0088 | 0.0100 | 0.0118 | 0.079 |
| 5,324 | 0.0063 | 0.0071 | 0.0083 | 0.240 |
| 10,648 | 0.0045 | 0.0051 | 0.0059 | 1.027 |

The floor falls as one over the square root of the count, the same in both
families (`venturi_tube`'s max 0.0083 at 5,324, `phone_stand`'s 0.0077); the
brute-force nearest search costs the square of it.

The ladder at 5,324 samples: d over all 200 bodies (min, median, max), and
the term at that median under each τ tried:

| Candidate | d min | median | max | τ = 0.02 | τ = 0.05 | τ = 0.1 | τ = 0.2 |
|---|---|---|---|---|---|---|---|
| floor (two seeds) | 0.0063 | 0.0071 | 0.0083 | 0.700 | 0.867 | 0.931 | 0.965 |
| moved 0.01 | 0.0070 | 0.0085 | 0.0107 | 0.655 | 0.844 | 0.919 | 0.959 |
| moved 0.03 | 0.0086 | 0.0143 | 0.0197 | 0.489 | 0.751 | 0.867 | 0.931 |
| moved 0.1 | 0.0190 | 0.0461 | 0.0682 | 0.100 | 0.398 | 0.631 | 0.794 |
| moved 0.3 | 0.0754 | 0.1562 | 0.2501 | 0.000 | 0.044 | 0.210 | 0.458 |
| turned 2° | 0.0033 | 0.0075 | 0.0095 | 0.686 | 0.860 | 0.927 | 0.963 |
| turned 7° | 0.0087 | 0.0147 | 0.0188 | 0.479 | 0.745 | 0.863 | 0.929 |
| turned 20° | 0.0094 | 0.0359 | 0.0477 | 0.166 | 0.488 | 0.699 | 0.836 |
| family's next | 0.0101 | 0.0487 | 2.5281 | 0.087 | 0.377 | 0.614 | 0.784 |

A move of 0.01 of the diagonal and a turn of 2° sit at the floor: no τ lets
the term tell them from the part itself at this count, and the IoU, which
has no floor on the exact route, carries them.

## Decision

**The surface term** (`reward/_surface.py`) is exp(−d/τ). Each body is
meshed at the reward config's chord fraction of its own diagonal and
sampled uniformly by area from a fresh `PCG64(seed)`, the config's seed for
both bodies, so bodies that mesh alike draw the same samples and score
exactly 1. d is the mean of the two one-way mean distances from a sample to
its nearest sample on the other body (brute force, in chunks), each mean a
`math.fsum`, over the target's bounding-box diagonal.

**Samples per body: 5,324, N/2 of ADR-0008's N** (the seed's share for the
surface). Its worst floor is 0.0083 at a quarter of a second; 10,648 lowers
it to 0.0059 at four times the cost, 2,662 raises it to 0.0118.

**τ = 0.05: the round value at least five times the worst floor** (6.0×
0.0083). The floor then costs a part built two ways at most
1 − e^(−0.0083/0.05) = 0.15 of the term, 0.02 of the reward
(0.9 · 0.15 · 0.15). Of the τ meeting that rule, 0.05 spreads the ladder
furthest: 0.75 at a move of 0.03, 0.40 at 0.1, 0.04 at 0.3; τ = 0.1 keeps
0.21 at 0.3, so a part a third of its size away still earns a fifth of the
term.

**exp is a fixed polynomial.** `exp_neg(x)` reduces x = n·ln 2 + r with ln 2
split in two (Cody and Waite, fdlibm's constants), evaluates e^(−r) by
Horner's rule on its Taylor series to degree 13, and scales by 2⁻ⁿ with
`math.ldexp`. Every operation is correctly rounded in a fixed order, so the
bits are the same on every machine; it is within 2 ulps of `math.exp`
(1 ulp measured over 3·10⁵ arguments), exactly 1 at 0 and 0 past 745.2.

**The other terms' formulas**, as plans/m4-reward fixed them, each in
[0, 1] and exactly 1 on identical inputs:

- `measures`: the mean of the volume ratio, the area ratio,
  1 − min(1, centroid gap / target diagonal) and the mean ratio of the
  sorted principal moments, every ratio min/max; the moments' eigenvalues
  by fixed Jacobi sweeps, never `np.linalg`.
- `topology`: w · Σmin/Σmax over the histogram of the seven surface kinds
  plus (1 − w) · 1/(1 + |Δgenus|), w the reward config's, ½ by default; no
  measurement here sets it.

## Consequences

- `RewardConfig` (plans/m4-reward step 5) carries `tau = 0.05`; the surface
  draws N/2 samples of its N. A change to either bumps the reward's version.
- A part built two ways loses up to 0.02 of its reward to the surface's
  floor; a self score is exactly 1 because both bodies read from the same
  bytes mesh alike. The floor depends only on the count, so a part with more
  faces does not pay more.
- The term reads a move below about 0.02 of the diagonal as noise; the IoU
  carries that range.
- d costs the square of the count: one surface term is about 0.13 s alone
  and 0.24 s under full load here, beside the IoU's sampled route.

## Alternatives considered

- **Point-to-mesh distance** (each sample to the other body's nearest
  triangle): no floor, only the chord's error, but a vectorised
  point–triangle distance with its seven regions and a search over every
  triangle for each sample. Kept for a later version if the floor ever
  dominates a table.
- **τ = 0.1 or 0.2**: twelve or twenty-four times the floor, but the term
  then barely moves before a third of the diagonal (0.63 and 0.79 at a move
  of 0.1).
- **τ = 0.02**: 2.4 times the floor; a part built two ways would lose 34%
  of the term.
- **10,648 samples**: a floor of 0.0059, so τ could be 0.03, for four times
  the time on every scored body.
- **`math.exp` or `np.exp`**: the platform's libm and the CPU's dispatch;
  their last bits can differ between machines.
