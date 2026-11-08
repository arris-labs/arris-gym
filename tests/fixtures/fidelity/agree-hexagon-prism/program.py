import arris.build as b

s = 1.7320508075688772
result = b.Workplane.XY().polygon([(2, 0), (1, s), (-1, s), (-2, 0), (-1, -s), (1, -s)]).extrude(3)
