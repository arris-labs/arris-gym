import cadquery as cq

result = cq.Workplane("XY").polyline([(0, 0), (2, 0), (2, 2)]).close().threePointArc((1, 3), (0, 2))
show_object(result)
