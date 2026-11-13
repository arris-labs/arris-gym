import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).lineTo(2, 0).lineTo(2, 2).close().cylinder(2, 1)
show_object(result)
