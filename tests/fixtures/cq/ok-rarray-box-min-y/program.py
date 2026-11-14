import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces("<Y").workplane().rarray(3, 1.5, 3, 2).hole(1)
show_object(result)
