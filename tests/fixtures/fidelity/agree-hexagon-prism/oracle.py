import cadquery as cq

s = 1.7320508075688772
result = cq.Workplane().polyline([(2, 0), (1, s), (-1, s), (-2, 0), (-1, -s), (1, -s)]).close().extrude(3)
