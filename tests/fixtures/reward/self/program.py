import arris.build as b

plate = b.Solid.box((0, 0, 0), (10, 10, 2))
result = plate.cut(b.Solid.cylinder((5, 5, -1), (0, 0, 1), 2, 4))
