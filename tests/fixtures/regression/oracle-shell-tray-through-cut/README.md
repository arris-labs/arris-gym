# Oracle volume of a chamfered tray after a through-cut

This reduces BenchCAD stem `sheet_metal_tray_017786_s20260505` to one
floor bore and one rectangular through-cut. Adapted from
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen`
at `5919f578ab09ec283603a082fab07c7639ab56eb`, under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

Use the [rim section integral](../../shells/README.md#chamfered-tray-prefixes)
in the XZ plane, with the opening at positive Y. The floor bore removes
a radius-2.105 cylinder of height t = 3.73 centred at x = 30, z = 0 and
halfway through the floor. It adds the cylinder wall and removes two disks.
The through-cut runs along Z across the floor and both walls. It is 16
wide in X and reaches 5 in from the outside floor, with its other half
outside the stock. It removes a 16 × 38.07 × t floor prism and two
16 × t × (5 − t) wall prisms. The cut replaces the exposed faces of those
prisms with their two common cross-sections normal to X and two ceiling
rectangles of area 16t. The cuts are disjoint and the stock bounds stay
fixed.

The fresh bore prefix has a relative volume gap of 8.71e-10. After
the through-cut, the recorded oracle reports 61199.67997017814 against
the construction's 61199.67989405608, a gap of 1.24e-9. The arris build
and the oracle STEP remeasured by arris both meet ADR-0005 against the
construction.
