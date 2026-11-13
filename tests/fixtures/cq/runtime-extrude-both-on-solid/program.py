import cadquery as cq

result = cq.Workplane("XY").box(1, 1, 1).extrude(1, both=True)
show_object(result)
