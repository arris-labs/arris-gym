import cadquery as cq

result = cq.Workplane("XY").circle(1).extrude(3)
show_object(result)
