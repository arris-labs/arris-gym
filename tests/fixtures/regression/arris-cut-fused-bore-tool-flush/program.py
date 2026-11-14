import arris.build as b

box = b.Solid.box((-5, -4, -2), (5, 4, 2))
bore = b.Solid.cylinder((2, 1, 2), (0, 0, -1), 0.5, 13.4)
counterbore = b.Solid.cylinder((2, 1, 2), (0, 0, -1), 1.0, 0.5)
result = box.cut(bore.fuse(counterbore))
