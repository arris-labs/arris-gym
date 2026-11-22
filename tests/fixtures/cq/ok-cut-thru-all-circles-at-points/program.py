import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(-3, -1), (2, 2)]).circle(0.5).cutThruAll()
show_object(result)
