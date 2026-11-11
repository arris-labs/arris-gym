import cadquery as cq
result = cq.Workplane('XY').box(1, 2, 3)
result = result.cut(cq.Workplane('XY').box(1, 1, 1))
