import cadquery as cq
first = cq.Workplane("XY").polygon(3, 4)
result = first.workplane(offset=3).polygon(3, 2).loft()
