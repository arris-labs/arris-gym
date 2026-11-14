import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().rarray(3, 4, 3, 2).hole(1)
show_object(result)
