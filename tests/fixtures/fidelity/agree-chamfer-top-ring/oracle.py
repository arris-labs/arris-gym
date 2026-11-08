import cadquery as cq

result = cq.Workplane().box(10, 10, 10, centered=False).faces('>Z').chamfer(1)
