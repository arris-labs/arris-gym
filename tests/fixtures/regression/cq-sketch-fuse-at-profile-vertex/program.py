import cadquery as cq

w = cq.Workplane("XY")
slanted = w.sketch().segment((-4, 4), (-2, 0)).segment((0, 1)).segment((-2, 5))
base = slanted.close().assemble().finalize().extrude(3)
other = w.sketch().push([(-6, 1)]).rect(12, 4).finalize().extrude(19)
r = base.union(other)
