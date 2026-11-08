import cadquery as cq

result = cq.Workplane().box(5, 3, 6, centered=False).translate((-1, 2, 3))
