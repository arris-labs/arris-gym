import cadquery as cq

result = cq.Workplane("XY").rect(0, 2).extrude(2)
show_object(result)
