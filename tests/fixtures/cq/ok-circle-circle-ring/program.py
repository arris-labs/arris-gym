import cadquery as cq

result = cq.Workplane("XY").circle(3).circle(1).extrude(2)
show_object(result)
