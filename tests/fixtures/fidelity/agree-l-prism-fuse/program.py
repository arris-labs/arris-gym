import arris.build as b

a = b.Solid.box((0, 0, 0), (4, 2, 2))
result = a.fuse(b.Solid.box((0, 2, 0), (2, 4, 2)))
