# ADR-0008: The IoU is exact where the kernel answers, and sampled on a jittered grid elsewhere

- Status: accepted
- Date: 2026-11-09

## Context

SEED.md §7.1 gives the IoU 0.6 of the reward and assumes a mesh winding
number over N points, half of them near the target's surface.
`docs/ARCHITECTURE.md` §The reward left two questions open: which method
answers the IoU until arris binds `classify_points`, and how the sampled
estimator treats points that are not volume-uniform. Step 1 of
plans/m4-reward built both routes in `reward/_iou.py`: the **exact route**,
the kernel's `interference` under a step budget, and the **sampled route**,
a winding number on each body's `tessellate` mesh. Their constants were left
to be measured here.

`tools/reward_calibrate.py` measured them on the C1 slice (BenchCAD
`code_gen` at `5919f578`, CC BY 4.0) on arris 0.10.0. The 300 programs run
under `cq` give 200 `ok` bodies (100 `phone_stand`, 100 `venturi_tube`; the
100 `lobed_knob` are refusals). Each body is the target of nine pairs built
by construction: itself; moved by 0.01, 0.03, 0.1 and 0.3 of its diagonal
and turned by 2°, 7° and 20° about its box's centre, each in a direction
drawn per pair from a seed; and the next body of its family as built. That
is 1,800 pairs, every one counted below. Seconds are wall-clock with 30
processes at once on one 32-thread machine, for the reader only.

**The exact route.** Each pair was asked at a cap of 10⁷ steps, then up a
ladder of half decades to the smallest budget that answers; every rung that
answered gave the cap's bits.

| Family, pairs | kind | exact answers | refused |
|---|---|---|---|
| `phone_stand`, 900 | all nine | 900 | 0 |
| `venturi_tube`, 100 each | self, neighbour, moved 0.01, turned 2° and 7° | 100 each | 0 |
| `venturi_tube`, 100 | moved 0.03 | 77 | 23 `OpUnsupportedError` |
| `venturi_tube`, 100 | moved 0.1 | 52 | 48 `OpUnsupportedError` |
| `venturi_tube`, 100 | moved 0.3 | 17 | 83 `OpUnsupportedError` |
| `venturi_tube`, 100 | turned 20° | 99 | 1 `OpUnsupportedError` |

1,645 of the 1,800 pairs answer; the 155 refusals are all a cone face
meeting a cone face, refused in at most 1.1 s; no pair reached the cap.

| Budget (steps) | pairs answered at or under, of 1,800 | slowest of them (s) |
|---|---|---|
| 10³ | 918 (0.510) | 0.26 |
| 10⁴ | 1,019 (0.566) | 1.55 |
| 10⁵ | 1,100 (0.611) | 1.55 |
| 10⁶ | 1,121 (0.623) | 7.59 |
| 3·10⁶ | 1,576 (0.876) | 16.77 |
| 10⁷ | 1,645 (0.914) | 17.02 |

Every box-built `phone_stand` pair answers at 10⁵ or under; the
`venturi_tube` pairs that answer mostly need 3·10⁶ (455 pairs, median
6.3 s) or 10⁷ (69 pairs, median 13.2 s).

**The sampled route.** On the 1,445 pairs the exact route answered, other
than the bodies against themselves, three draws were tried against the
exact IoU, each point classed by the winding number on both meshes:

- **uniform**: independent uniform points in the box holding both bodies,
  step 1's draw;
- **jittered**: the box cut into k³ equal cells, one uniform point in each,
  k the rounded cube root of N;
- **refined**: strata by cell with weights, a quarter of N classing k³ cell
  centres, a cell whose centre's class differs from a neighbour's taking an
  equal share of the spare points, each cell weighted by its volume; the
  strata come from the fixed centres, so the weights are exact.

Errors are estimate minus exact; the RMSE is over all 1,445 pairs, and over
the 645 `venturi_tube` pairs, the curved family the sampled route serves.

| Draw | N | chord | bias | RMSE | worst | RMSE, `venturi_tube` | median s |
|---|---|---|---|---|---|---|---|
| uniform | 2,000 | 1/200 | −0.0009 | 0.0244 | 0.107 | 0.0190 | 0.058 |
| uniform | 5,000 | 1/200 | −0.0009 | 0.0162 | 0.097 | 0.0124 | 0.145 |
| uniform | 10,000 | 1/200 | −0.0011 | 0.0110 | 0.052 | 0.0090 | 0.287 |
| uniform | 20,000 | 1/200 | −0.0011 | 0.0081 | 0.035 | 0.0071 | 0.579 |
| jittered | 2,197 | 1/200 | −0.0005 | 0.0205 | 0.084 | 0.0170 | 0.064 |
| jittered | 4,913 | 1/200 | −0.0009 | 0.0133 | 0.066 | 0.0110 | 0.143 |
| jittered | 10,648 | 1/200 | −0.0008 | 0.0092 | 0.036 | 0.0076 | 0.310 |
| jittered | 19,683 | 1/200 | −0.0009 | 0.0069 | 0.032 | 0.0064 | 0.580 |
| refined | 2,000 | 1/200 | −0.0013 | 0.0237 | 0.113 | 0.0200 | 0.054 |
| refined | 5,000 | 1/200 | −0.0015 | 0.0127 | 0.046 | 0.0121 | 0.137 |
| refined | 10,000 | 1/200 | −0.0010 | 0.0086 | 0.035 | 0.0083 | 0.272 |
| refined | 20,000 | 1/200 | −0.0010 | 0.0058 | 0.027 | 0.0061 | 0.545 |

The chord, with the jittered draw at 19,683 points (bias on `venturi_tube`
in brackets; a `phone_stand` is planar and meshes exactly at every chord):

| Chord (of each body's diagonal) | bias | RMSE | bias, `venturi_tube` | median s |
|---|---|---|---|---|
| 1/50 | −0.0054 | 0.0131 | (−0.0125) | 0.468 |
| 1/100 | −0.0047 | 0.0124 | (−0.0109) | 0.473 |
| 1/200 | −0.0009 | 0.0069 | (−0.0023) | 0.580 |
| 1/400 | −0.0003 | 0.0064 | (−0.0010) | 0.688 |

The bias is negative and the chord's: a mesh inscribed in a curved face
holds less volume than the face. The smallest union a pair offers, a thin
`phone_stand` against itself moved 0.3 of its diagonal, holds at least 304
of 10,648 jittered points in expectation (a neighbour pair at least 520),
so no pair of the slice meets the empty case.

The winding number's chunk was also measured: at 2¹⁸ points-times-triangles
a chunk took 0.41 s alone and 4.5 s with sixteen processes at once (out of
cache); at 2¹⁴, 0.31 s and 0.36 s. `CHUNK_ELEMENTS` is 2¹⁴; it moves no
result.

## Decision

**The exact route answers first.** `interference` under the reward
config's `iou_budget`: `apart` or `touching` is 0; both containment flags
are exactly 1; one flag is the smaller volume over the larger; otherwise
`v∩ / (vA + vB − v∩)`, clamped to [0, 1]. Any `ArrisError`, the spent
budget's `Interrupted` included, sends the pair to the sampled route, and
the score's `iou_route` says which answered.

**`iou_budget` is 10⁷ steps.** It answers every slice pair the kernel can
answer. The slowest answer took 17.0 s, and a pair that needed only 3·10⁶
steps took 16.8 s, so a cap of 3·10⁶ would send 69 more pairs to sampling
for almost no shorter worst case; 10⁶ would send 38% of all pairs (524
more) to bring it to 7.6 s. A step count, never a wall-clock limit, so
which route answers is the same on every machine.

**The sampled route draws a jittered grid.** One uniform point from
`PCG64(seed)` in each of k³ equal cells of the box that holds both bodies,
k the largest integer with k³ ≤ N (integer arithmetic). Each body is meshed
at a chord of **1/200** of its own diagonal, so bodies built alike mesh
alike. The estimate is the count inside both over the count inside either;
its error is at most the binomial one over the points inside either.
**N is 10,648 (22³)**: RMSE 0.0092 against the exact route (0.0076 on the
curved family), worst 0.036, a third of a second.

**The near-surface points are dropped from the IoU.** The seed's N/2 points
near the target's surface feed only the `surface` term (ADR-0009); the IoU
counts only its own jittered draw. Counting them unweighted biases the IoU
and was not a candidate; weighting them needs their density, which a
surface offset kernel does not give in closed form, so the weighted
candidate measured was the refined draw's strata by cell.

## Consequences

- The defaults go into `RewardConfig` (plans/m4-reward step 5) as
  `iou_budget = 10_000_000`, `chord = 1/200`, `points = 10_648`, and a
  change to any of them bumps the reward's version.
- Every `phone_stand` pair is exact; 155 of 900 `venturi_tube` pairs are
  sampled, and so is every pair the kernel refuses beyond the slice, until
  arris answers cone against cone or binds `classify_points` (the ask is
  filed by plans/m4-reward step 10 with these counts). A table counts
  `iou_route`.
- The sampled route's RMSE of 0.009 is 0.005 of a reward (0.9 · 0.6 of
  it), and its bias of −0.002 on curved parts 0.001: a candidate that is the
  target exactly still scores exactly 1, since identical meshes class every
  point alike.
- A pair the exact route answers near its cap takes up to 17 s here under
  full load; the score worker's deadline (step 6) has to stay well above
  it, and a `timeout` while scoring is counted, never silent.
- `inside`'s chunk is sized for many workers at once, not for one alone.

## Alternatives considered

- **A wall-clock switch between routes**: a slower machine would send to
  the sampled route a pair a faster one answers exactly, moving its score.
- **A cap of 10⁶ steps**: worst case 7.6 s, but 38% of all pairs on the
  sampled route against 8.6%.
- **The uniform draw** (step 1's): above the jittered draw's RMSE at every
  N, by 0.002 at 10,000 points.
- **The refined draw**: 0.0006 below the jittered draw's RMSE at 10,000
  points over all pairs, but above it on `venturi_tube` at every N up to
  10,000 and 0.0003 below at 20,000; worse at 2,000 points (worst 0.113); a
  pilot pass and weights for no gain on the family the sampled route
  serves.
- **A chord of 1/400**: bias −0.0010 on curved parts against −0.0023, for
  40% more time on `venturi_tube`; the sampling error dominates either way.
- **19,683 points**: RMSE 0.0069 for twice the time.
- **The seed's near-surface points counted with the uniform N**: biased
  upward near the boundary, as ARCHITECTURE.md said; not measured.
