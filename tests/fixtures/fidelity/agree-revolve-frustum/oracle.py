import cadquery as cq

result = cq.Workplane('XZ').polyline([(0, 0), (2, 0), (1, 3), (0, 3)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
