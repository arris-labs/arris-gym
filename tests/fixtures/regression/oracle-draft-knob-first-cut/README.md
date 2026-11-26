# First flute cut in a drafted knob

This prefix of `knob_000063_s20260506` comes from BenchCAD/BenchCAD
`code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`
(CC-BY-4.0). The stock before the cut is the `knob-prefix` program in
`tapers/contexts.json`.

The two drafts and the cylinder have total volume 2130.94436037940
by the frustum and cylinder formulas. The cutter reaches only the
second draft and the end cylinder. Its axis is parallel to the stock's
axis at a distance of 5.05. At each axial coordinate, compute the
intersection area of a disc of radius 0.87 and the stock's disc by
adding the areas of their two circular segments. Begin where the
increasing radius of the outward draft reaches 5.05 − 0.87, split
the integral at the cone-to-cylinder joint, and stop at the smaller
of the cylinder end and the cutter end. On the cylinder the area is
constant. On the draft, Gauss–Legendre quadrature at 64, 128 and 256
nodes gives removed volume 7.164880414458, 7.164880414606 and
7.164880414611. The remaining volume is 2123.77947996479.

`oracle.json` records the exact `oracle.py` through CadQuery 2.3.0
and Open CASCADE 7.9.3.0. The recorded oracle volume is
2123.77987169735. Arris measures 2123.77948000459. The strict
expected failure holds the oracle to the independent volume.
