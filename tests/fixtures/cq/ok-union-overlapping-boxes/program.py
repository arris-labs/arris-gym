import cadquery as cq

a = cq.Workplane("XY").box(2, 2, 2)
b = cq.Workplane("XY").transformed(offset=cq.Vector(1, 1, 1)).box(2, 2, 2)
show_object(a.union(b))
