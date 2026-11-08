import arris.build as b

plate = b.Solid.box((0, 0, 0), (10, 10, 10))
result = plate.hole(b.Workplane.XY(10).at([(5, 5)]), 4, 6)
