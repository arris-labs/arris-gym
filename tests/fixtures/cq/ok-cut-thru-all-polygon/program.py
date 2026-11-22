import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().polygon(4, 4).cutThruAll()
show_object(result)
