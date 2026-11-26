import cadquery as cq
stock = cq.Workplane("XY").box(10, 8, 6)
result = stock.union(stock.translate((14, 0, 0))).faces(">Z").shell(-1)
