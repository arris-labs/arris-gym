import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).threePointArc((1, 0), (2, 0)).lineTo(1, 2).close().extrude(1)
show_object(result)
