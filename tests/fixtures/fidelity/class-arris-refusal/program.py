import arris.build as b

box = b.Solid.box((0, 0, 0), (6, 4, 3))
result = box.fillet(box.edges().parallel((0, 1, 0)).extreme((-1, 0, 1)), 10)
