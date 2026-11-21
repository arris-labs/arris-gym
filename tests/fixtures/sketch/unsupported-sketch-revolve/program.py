import cadquery as cq

w = cq.Workplane("XY").box(4, 4, 4).workplane(offset=2).sketch().push([(3, 2)]).rect(5, 5).finalize()
result = w.revolve(360, (-1, 0, 0), (-1, 1, 0))
