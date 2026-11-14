import cadquery as cq

result = cq.Workplane("XY").moveTo(5, 5).polyline([(0, 0), (3, 0), (0, 4)]).close().extrude(2)
show_object(result)
