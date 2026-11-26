import cadquery as cq
stock = cq.Workplane("XY").box(10, 8, 6)
result = stock.faces(">Z").shell(float("nan"))
