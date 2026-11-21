import cadquery as cq

w = cq.Workplane("XY")
base = w.sketch().push([(-7.5, 5)]).rect(31, 16).finalize().extrude(-25)
post = w.sketch().push([(-7, 0)]).circle(3).finalize().extrude(19)
r = base.union(post)
