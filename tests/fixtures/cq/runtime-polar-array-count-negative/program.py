import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().polarArray(3, 0, 360, -1).hole(1)
show_object(result)
