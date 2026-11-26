import cadquery as cq
stock = cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 45)).box(8, 8, 6)
result = stock.faces(">X").shell(-1)
