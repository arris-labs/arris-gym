import cadquery as cq

result = cq.Workplane("XY").box(2, 2, 2)
show_object(result)
