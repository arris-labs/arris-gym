import cadquery as cq

section = cq.Workplane("XY").transformed(rotate=cq.Vector(1, 0, 0)).circle(1)
result = section.workplane(offset=1).circle(2).loft()
