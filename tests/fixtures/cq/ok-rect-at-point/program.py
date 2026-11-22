import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).rect(4, 2).extrude(2)
show_object(result)
