import cadquery as cq

result = cq.Workplane('XZ').polyline([(1, 0), (3, 0), (3, 2), (1, 2)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
