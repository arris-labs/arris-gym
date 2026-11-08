import cadquery as cq

result = cq.Workplane('XZ').moveTo(0, -2).threePointArc((2, 0), (0, 2)).close().revolve(360, (0, 0, 0), (0, 1, 0))
