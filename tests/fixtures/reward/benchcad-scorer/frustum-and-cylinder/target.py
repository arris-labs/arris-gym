import cadquery as cq

result = cq.Workplane("XY").polyline([(0, 0), (2, 0), (2, 3), (0, 3)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
show_object(result)
