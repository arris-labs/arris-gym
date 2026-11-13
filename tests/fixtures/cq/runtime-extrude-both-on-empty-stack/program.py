import cadquery as cq

result = cq.Workplane("XY").extrude(1, both=True)
show_object(result)
