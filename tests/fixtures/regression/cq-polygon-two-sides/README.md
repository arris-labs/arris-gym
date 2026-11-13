# cq-polygon-two-sides

`polygon(2, 4).extrude(1)`, read on the oracle while lifting `polygon`
(plans/lift-polygon step 2, 2026-11-14): CadQuery 2.3.0 builds the wire from
(2, 0) to (-2, 0) and back and extrudes it into a solid of zero volume and
area 8 that its checker passes, `ok` (`oracle.json`, that run's recorded
report). `cq` ends it `runtime` (`ValueError`, "fewer than three sides
enclose no area"). `Workplane.polygon(num, num)` is in the subset, so the
row is `cq_bug` (ADR-0012: a declined behaviour of an admitted form is never
`by_design`), counted until `cq` builds it or the form leaves the subset.

Desired: `ok`, agreeing with the oracle: the closed form of `expected.json`'s
`note`, its centroid the oracle's since a zero volume has none. Marked strict
`xfail`; `test_cq_polygon.py` also holds the row to agreement with
`oracle.json`, strict `xfail`. Not an arris finding: `cq` refuses before the
kernel sees the profile.
