import arris.build as b

box = b.Solid.box((0, 0, 0), (10, 10, 10))
result = box.chamfer(box.faces().normal((0, 0, 1)).edges(), 1)
