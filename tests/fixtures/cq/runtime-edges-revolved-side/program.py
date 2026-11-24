import cadquery as cq

result = cq.Workplane("XY").polyline([(0, -2), (2, -2), (2, 2), (0, 2)]).close().revolve(360, (0, -2, 0), (0, 2, 0)).edges(">X")
show_object(result)
