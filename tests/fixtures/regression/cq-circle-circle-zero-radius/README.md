# cq-circle-circle-zero-radius

`circle(2).circle(0).extrude(2)`, read on the oracle while lifting a second
`circle` on a stack holding one (plans/lift-face-selectors step 7a): CadQuery
2.3.0 builds the plain cylinder of the first circle, `ok` (`oracle.json`,
that run's recorded report). `cq` refuses the radius-0 circle,
`unsupported_api`. `Workplane.circle` is in the subset, so the row is
`cq_bug` (ADR-0012), counted until `cq` builds it. No BenchCAD or CAD-Recode
program is known to draw it.

Desired: `ok`, the closed form of `expected.json`'s `note`. Marked strict
`xfail`. Not an arris finding: `cq` refuses before the kernel sees the profile.
