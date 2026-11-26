import cadquery as cq

stock = cq.Workplane("XZ").box(96.89, 38.07, 55.57).edges(">Y").chamfer(0.96)
cup = stock.faces(">Y").shell(-3.73)
drilled = cup.faces("<Y").workplane().pushPoints([(30, 0)]).hole(4.21)
result = drilled.faces(">Z").workplane().rect(16, 10).cutThruAll()
