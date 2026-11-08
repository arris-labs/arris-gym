import arris.build as b

result = b.Solid.box((0, 0, 0), (10, 10, 10)).cut(b.Solid.box((6, 6, -1), (11, 11, 11)))
