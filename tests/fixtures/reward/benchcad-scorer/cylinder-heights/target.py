import cadquery as cq

result = cq.Workplane("XY").circle(1).extrude(2)
show_object(result)
