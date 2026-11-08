import cadquery as cq

a = cq.Workplane().box(4, 2, 2, centered=False)
result = a.union(cq.Workplane().box(2, 2, 2, centered=False).translate((0, 2, 0)))
