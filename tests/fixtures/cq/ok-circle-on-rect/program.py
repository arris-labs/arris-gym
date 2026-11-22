import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).rect(6, 4).circle(1).extrude(2)
show_object(result)
