import arris.build as b

box = b.Solid.box((0, 0, 0), (10, 10, 10))
result = box.fillet(box.edges().parallel((0, 0, 1)), 2)
