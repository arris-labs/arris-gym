import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).fillet(1)
show_object(result)
