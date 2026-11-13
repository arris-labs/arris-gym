import cadquery as cq

result = cq.Workplane("XY").polygon(5, -4).extrude(2)
show_object(result)
