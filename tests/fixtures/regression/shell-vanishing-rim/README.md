# Inward shell whose cavity closes below the rim

Chamfering the four top edges of a centred 10 × 8 × 6 box by 3.9
leaves a 2.2 × 0.2 top face. Measure depth `d` inward from that face
at z = 3. A section with lengths `a`, `b` and chamfer depth `q` has
side lengths `a − 2 max(q − d, 0)` and `b − 2 max(q − d, 0)`.
The outer stock uses (10, 8, 3.9) over depths 0 to 6.

The one-unit inward offset moves the side planes by 1 and the
chamfer planes by √2 in their equations. The cavity uses (8, 6,
2.9 + √2). Its short side first reaches zero at depth √2 − 0.1,
below the rim, and the floor is at depth 5. The material therefore
has a sealed cavity inside the original exterior. Subtract the
section integral of the cavity from the stock to get volume. The
same integrals weighted by `3 − d` give the first Z moment. Surface
area is both boundaries' section perimeter integrated with factor
√2 through the chamfer and factor 1 along the vertical sides, plus
the two stock caps and the cavity floor. The cavity closes along a
line, which contributes zero area.

arris 0.12.0 returns `OpDegenerateError` with
`degenerate result: the offset would make the edge or face vanish or turn inside out (+e16)`.
The pinned oracle and its STEP remeasurement agree with the
construction. The STEP contains one solid with two shells.

Replay the oracle with
`uv run --locked python tools/oracle_run.py tests/fixtures/regression/shell-vanishing-rim/oracle.py --out .scratch/shell-vanishing-rim-oracle.jsonl`.
