import cadquery as cq

result = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
show_object(result)
