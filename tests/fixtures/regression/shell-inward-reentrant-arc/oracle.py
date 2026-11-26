import cadquery as cq
stock = cq.Workplane("XY").polyline([(0, 0), (8, 0), (8, 4), (4, 4), (4, 8), (0, 8)]).close().extrude(6)
result = stock.faces(">Z").shell(-1)
