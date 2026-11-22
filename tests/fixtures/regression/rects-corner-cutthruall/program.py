import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(0, 0), (2, 2)]).rect(2, 2).cutThruAll()
show_object(result)
