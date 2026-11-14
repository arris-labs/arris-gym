import cadquery as cq

result = cq.Workplane("XZ").moveTo(2, 1).circle(3).circle(1).extrude(2)
show_object(result)
