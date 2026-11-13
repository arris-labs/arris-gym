import cadquery as cq

result = cq.Workplane("XY").moveTo(1, 1).lineTo(2, 1).cylinder(2, 1)
show_object(result)
