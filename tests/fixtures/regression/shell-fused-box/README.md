# Shell after fusing overlapping boxes

Two 10 × 8 × 6 boxes whose centres differ by 8 along X overlap by 2.
Their union is an 18 × 8 × 6 box centred at (4, 0, 0). Opening the top
and offsetting inward by 1 subtracts a 16 × 6 × 5 cavity centred at
(4, 0, 0.5). The material volume is 864 − 480 = 384 and its centroid is
(4, 0, −0.625). The box has area 600. The opening removes 96, and the
cavity floor and walls add 316, for area 820.

On arris 0.12.0 the union has 14 planar faces. The shell returns
`OpInternalError` with `kernel bug: a skin edge appended was not found`.
The same shell on a single 18 × 8 × 6 box centred at (4, 0, 0)
agrees with the construction. The pinned oracle builds the union case
and its STEP remeasurement agrees with the construction.

Replay the oracle with
`uv run --locked python tools/oracle_run.py tests/fixtures/regression/shell-fused-box/oracle.py --out .scratch/shell-fused-box-oracle.jsonl`.
