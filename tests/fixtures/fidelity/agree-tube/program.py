import arris.build as b

outer = b.Workplane.XY().circle(3).extrude(4)
result = outer.cut(b.Solid.cylinder((0, 0, -1), (0, 0, 1), 1, 6))
