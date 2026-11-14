import cadquery as cq

result = cq.Workplane("XY").circle(2).circle(2).extrude(2)
show_object(result)
