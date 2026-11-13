import cadquery as cq

result = cq.Workplane("XY").polygon(6, 0).extrude(1)
show_object(result)
