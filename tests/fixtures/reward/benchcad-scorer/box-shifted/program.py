import cadquery as cq

result = cq.Workplane("XY").box(4, 2, 2)
show_object(result)
