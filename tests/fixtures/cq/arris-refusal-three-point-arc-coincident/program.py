import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).lineTo(2, 0).threePointArc((1, 1), (1, 1)).lineTo(0, 2).close().extrude(1)
show_object(result)
