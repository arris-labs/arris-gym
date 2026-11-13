import cadquery as cq

result = cq.Workplane("XY").moveTo(3, 1).circle(3).sphere(1)
show_object(result)
