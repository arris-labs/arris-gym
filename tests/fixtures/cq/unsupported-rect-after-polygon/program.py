import cadquery as cq

result = cq.Workplane("XY").polygon(4, 4).rect(2, 1).extrude(2)
show_object(result)
