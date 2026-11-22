import cadquery as cq

result = cq.Workplane("XY").rect(4, 0).extrude(2)
show_object(result)
