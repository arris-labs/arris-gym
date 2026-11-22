import cadquery as cq

result = cq.Workplane("XY").slot2D(6, 2, 0).extrude(2, both=True)
show_object(result)
