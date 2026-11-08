import arris.build as b

plate = b.Solid.box((0, 0, 0), (20, 10, 5))
result = plate.hole(b.Workplane.XY(5).at([(5, 5), (15, 5)]), 2)
