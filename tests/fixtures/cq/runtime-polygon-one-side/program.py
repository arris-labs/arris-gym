import cadquery as cq

result = cq.Workplane("XY").polygon(1, 4).extrude(1)
show_object(result)
