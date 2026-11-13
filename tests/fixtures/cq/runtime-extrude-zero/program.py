import cadquery as cq

result = cq.Workplane("XY").circle(1).extrude(0)
show_object(result)
