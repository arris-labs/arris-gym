import cadquery as cq

result = cq.Workplane("XY").moveTo(5, 0).circle(1).extrude(2).sphere(0.5)
show_object(result)
