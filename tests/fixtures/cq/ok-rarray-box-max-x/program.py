import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">X").workplane().rarray(2, 1.5, 2, 2).hole(1)
show_object(result)
