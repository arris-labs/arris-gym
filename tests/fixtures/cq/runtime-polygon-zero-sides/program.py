import cadquery as cq

result = cq.Workplane("XY").polygon(0, 4).extrude(1)
show_object(result)
