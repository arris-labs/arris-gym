import cadquery as cq

result = cq.Workplane("YZ").polyline([(0, 0), (4, 0), (4, 2), (2, 1), (2, 4), (0, 4)]).mirrorY().extrude(3)
