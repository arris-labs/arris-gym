import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().rarray(2, 3, 1, 1).hole(1)
show_object(result)
