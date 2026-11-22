import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).circle(3).rect(2, 1).extrude(2)
show_object(result)
