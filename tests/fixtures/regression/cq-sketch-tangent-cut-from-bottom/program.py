import cadquery as cq

w = cq.Workplane("XY")
r = w.sketch().rect(10, 8).push([(0, -2)]).circle(2, mode="s").finalize().extrude(5)
