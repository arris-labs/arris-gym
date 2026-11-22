import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).slot2D(6, 2, 90).extrude(2)
show_object(result)
