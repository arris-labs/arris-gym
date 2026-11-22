import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(-2, 0), (2, 0)]).slot2D(6, 2, 90).cutThruAll()
show_object(result)
