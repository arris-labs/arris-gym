import cadquery as cq

result = cq.Workplane("XY").rect(4, -2).extrude(2)
show_object(result)
