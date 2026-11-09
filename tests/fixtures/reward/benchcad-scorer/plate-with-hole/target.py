import cadquery as cq

result = cq.Workplane("XY").box(6, 4, 1)
show_object(result)
