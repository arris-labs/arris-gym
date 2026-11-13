import cadquery as cq

result = cq.Workplane("XY").moveTo(1, 1).lineTo(2, 1).sphere(1)
show_object(result)
