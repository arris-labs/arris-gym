import cadquery as cq

result = cq.Workplane("XY").moveTo(1, 1).lineTo(2, 1).polygon(6, 1).extrude(1)
show_object(result)
