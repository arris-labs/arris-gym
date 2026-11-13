import cadquery as cq

result = cq.Workplane("XY").moveTo(5, 0).circle(1).extrude(2).polygon(6, 1).extrude(1)
show_object(result)
