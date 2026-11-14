import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().polarArray(0, 0, 360, 3).hole(1)
show_object(result)
