import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">X").workplane().polarArray(1.5, 0, 90, 2).hole(0.8)
show_object(result)
