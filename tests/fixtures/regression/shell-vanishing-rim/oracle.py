import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 6).edges(">Z").chamfer(3.9).faces(">Z").shell(-1)
