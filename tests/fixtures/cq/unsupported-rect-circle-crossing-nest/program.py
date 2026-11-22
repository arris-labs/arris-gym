import cadquery as cq

result = cq.Workplane("XY").rect(4, 2).circle(1.5).extrude(2)
show_object(result)
