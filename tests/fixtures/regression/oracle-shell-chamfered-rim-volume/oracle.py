import cadquery as cq
stock = cq.Workplane("XY").box(10, 8, 6).edges(">Z").chamfer(1)
result = stock.faces(">Z").shell(-0.5)
