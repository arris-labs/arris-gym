import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).lineTo(1, 0).lineTo(1, 1).close().extrude(1, both=True)
show_object(result)
