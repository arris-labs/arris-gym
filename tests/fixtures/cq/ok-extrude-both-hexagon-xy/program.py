import cadquery as cq

result = cq.Workplane("XY").polygon(6, 2).extrude(1.5, both=True)
show_object(result)
