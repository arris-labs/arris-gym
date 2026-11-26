import cadquery as cq

result = cq.Workplane("XY").polyline([(0, 0), (3, 0), (3, 1), (1, 1), (1, 5), (3, 5), (3, 6), (0, 6)]).mirrorY().extrude(4)
