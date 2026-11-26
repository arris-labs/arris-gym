import cadquery as cq

section = cq.Workplane("XY").polygon(49, 20)
upper = section.transformed(rotate=cq.Vector(0, 0, 180 / 49 - 1), offset=cq.Vector(0, 0, 8))
result = upper.polygon(49, 16).loft()
