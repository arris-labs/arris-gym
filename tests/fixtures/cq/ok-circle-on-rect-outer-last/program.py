import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).rect(2, 1).circle(3).extrude(2)
show_object(result)
