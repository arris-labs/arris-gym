# Shell probes

The offset probes run through the `arris` dialect. The `cq` shell tests
reuse the closed forms and run the supported call through the sandbox.
Each `oracle.py` has a report
from CadQuery 2.3.0 with OCCT 7.9.3.0. The gate reads those reports offline.
Replay them through the oracle worker using the synced environment.

```sh
uv run --locked python tools/oracle_run.py tests/fixtures/shells/*/oracle.py \
  tests/fixtures/regression/{shell-*,oracle-shell-chamfered-rim-volume}/oracle.py \
  --out .scratch/shell-oracle.jsonl
```

The fixture reports keep the `report` object with `seconds` omitted. The
NaN probe reached the oracle's default 30 s deadline. `zero` and `infinite`
record oracle runtime errors. `too-thick` records that returning the
original box is possible on the oracle while arris refuses the offset.
`missing` has only oracle evidence because `Solid.shell` itself has a
solid receiver.

## Box and cylinder constructions

The centred box is 10 × 8 × 6. A one-unit inward shell through the top
subtracts an 8 × 6 × 5 cavity whose centre is at z = 0.5. Opening the
right and top faces subtracts a 9 × 6 × 5 cavity centred at (0.5, 0, 0.5).
With no open face the subtracted box is 8 × 6 × 4, centred at the origin.
The surface area sums the surviving exterior, cavity and rim faces.
Selecting edges also makes the sealed cavity in CadQuery.
`parent-selection` checks that an intervening `workplane()` clears the
opening selection. In `adjacent-selected` a square box turned 45° around
Z gives two tied faces under `>X`, both of which become openings.

The through bore removes a one-unit-high cylinder from the open box's
floor. Its two radius-1 disks have the same total area as the
added cylinder wall. Its volume is π and its centre is at z = −2.5.
The cylinder probe subtracts a radius-4 cylinder of height 5 starting
at z = 1 from a radius-5 cylinder of height 6 starting at z = 0.

For the outward box with intersection joins, the outer box grows to
12 × 10 × 7, centred at z = −0.5. The original box is the cavity. The
L-shaped prism's intersection-join control subtracts a height-5 cavity
with cross-section `[1,7] × [1,7]` less `[3,7] × [3,7]`. The default
arc joins have separate regression fixtures.

The compound probes repeat the same constructions with a copy
translated 14 units in x. When only one top face is selected the other
piece gets a sealed cavity in arris. CadQuery fails with all, one or no
open faces. Shelling the sealed box again also fails on the oracle.
The arris construction removes a 9.5 × 7.5 × 5.75 cavity from the
original exterior and leaves a 0.25-thick wall around the original
interior, bounded by an 8.5 × 6.5 × 4.5 box.

## Chamfered tray prefixes

| Fixture | BenchCAD stem | Open face |
|---|---|---|
| `rim-xy` | `sheet_metal_tray_000257_s20260505` | `>Z` |
| `rim-xz` | `sheet_metal_tray_000130_s20260505` | `>Y` |
| `rim-yz` | `sheet_metal_tray_000468_s20260505` | `>X` |

Adapted from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD),
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
Each prefix stops at the shell and adds assertions for the selected
stock face and the rim.

Let the stock have transverse lengths L and W, height H and chamfer c.
Measure depth d inward from the selected plane. For example, the
positive first side is x = L/2, and its chamfer plane is
x − d = L/2 − c. Inward thickness t moves the side plane by t and
the chamfer plane by √2 t in its equation because its normal has length
√2. The floor moves from d = H to H − t. At the opening the
outer rim loop has dimensions (L − 2c, W − 2c), and the inner rim
loop subtracts another 2√2 t from each dimension.

For a rectangular section with lengths a, b, height h and chamfer
depth q, the depth-d area is
`(a − 2 max(q − d, 0))(b − 2 max(q − d, 0))`.
Use (L, W, H, c) for the stock and
(L − 2t, W − 2t, H − t, c + (√2 − 1)t) for the void.
Integrate area and d times area to get volume and the first moment.
For the lateral area, integrate the perimeter with factor √2 across
the chamfer and factor 1 below it. Add both rectangular floors and
the difference of the loop areas at the rim. Each body has 19 faces,
one shell and one solid.

The pinned oracle's reported excess volume is about 0.000030, 0.000117
and 0.000343 respectively. These exceed ADR-0005's relative volume limit.
The gate validates `occt_wrong` verdicts with the closed forms. In the
Step 1 inspection, remeasuring the oracle STEPs with `read_target` gave
17058.04247191795, 111726.13863642217 and 117781.00745118159.
All three meet the agreement tolerance against the corresponding
arris body. The [reduced probe](../regression/oracle-shell-chamfered-rim-volume/)
keeps the oracle measurement discrepancy.
