import cadquery as cq

a = cq.Workplane("XY").transformed(offset=cq.Vector(1, 0, 0)).box(2, 2, 2)
b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 1)).box(2, 4, 4)
show_object(a.union(b))
