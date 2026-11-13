import cadquery as cq

result = cq.Workplane("XY").box(1, 1, 1).union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(1, 1, 1)).threePointArc((1, 1), (2, 0))
show_object(result)
