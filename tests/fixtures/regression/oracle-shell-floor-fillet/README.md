# Oracle volume of a filleted enclosure floor

This reduces BenchCAD stem `enclosure_001465_s20260505` to the shell and
four outside bottom-edge fillets. The shell alone agrees; the gap persists
after removing the bore array. Adapted from
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen`
at `5919f578ab09ec283603a082fab07c7639ab56eb`, under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

Let L, W, H be the box dimensions, t the wall thickness and r the fillet
radius. The cavity stays rectangular because r < t. At height u above the
outside floor, for 0 ≤ u ≤ r, each side moves in by
`s = r − sqrt(r² − (r − u)²)`. The four cylinders meet at their
bisectors, so the section remains a rectangle. Integrate
`L W − (L − 2s)(W − 2s)` and its product with `u − H/2`
to get the removed volume and first moment. Subtract those and the cavity
contributions from the stock. For the area, replace the outside floor
with the inset rectangle and replace the height-r perimeter strip
with the integral of `2(L + W − 4s)` over the quarter-circle arc.

The integral gives volume 42469.286112761685. The recorded oracle
gives 42469.286214357926, a relative gap of 2.39e-9. The arris build and
the oracle STEP remeasured by arris both meet ADR-0005 against the integral.
