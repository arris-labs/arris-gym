import cadquery as cq

section = cq.Workplane("XY").polygon(9, 20)
upper = section.transformed(rotate=cq.Vector(0, 0, 180 / 9 - 1), offset=cq.Vector(0, 0, 8))
result = upper.polygon(9, 16).loft()
