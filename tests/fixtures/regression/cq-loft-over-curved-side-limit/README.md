# Two-section loft above the curved side count limit

The refused bevel gears and two-section helical gears hit the side count
limit in ADR-0026. The 49-sided twisted polygon from
`lofts/runtime-contexts.json` exercises the first count above that limit.
The two nested convex outlines at Z = 0 and Z = 8 define the two caps
of a single solid. CadQuery 2.3.0 and Open CASCADE 7.9.3.0 build it as
recorded in `oracle.json`. The strict regression holds the subset
to that result while the separate context test exercises the current guard.
