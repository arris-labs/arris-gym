import cadquery as cq

result = cq.Workplane("XY").box(4, 4, 4)
show_object(result)
