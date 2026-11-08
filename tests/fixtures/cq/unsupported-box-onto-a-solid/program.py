import cadquery as cq

result = cq.Workplane("XY").box(2, 2, 2).box(1, 1, 4)
show_object(result)
