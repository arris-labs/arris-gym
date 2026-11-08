import cadquery as cq

a = cq.Workplane("XY").box(1, 1, 1)
b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(1, 1, 1)
show_object(a.union(b))
