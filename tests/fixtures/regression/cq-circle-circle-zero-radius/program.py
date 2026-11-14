import cadquery as cq

result = cq.Workplane("XY").circle(2).circle(0).extrude(2)
show_object(result)
