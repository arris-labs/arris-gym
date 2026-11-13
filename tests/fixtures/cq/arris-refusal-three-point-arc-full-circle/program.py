import cadquery as cq

result = cq.Workplane("XY").moveTo(2, 0).threePointArc((-2, 0), (2, 0)).close().extrude(1)
show_object(result)
