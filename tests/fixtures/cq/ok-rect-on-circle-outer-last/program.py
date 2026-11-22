import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).circle(1).rect(6, 4).extrude(2)
show_object(result)
