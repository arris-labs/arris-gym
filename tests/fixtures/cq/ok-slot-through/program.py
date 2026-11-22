import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().center(1, -1).slot2D(6, 2, 45).cutThruAll()
show_object(result)
