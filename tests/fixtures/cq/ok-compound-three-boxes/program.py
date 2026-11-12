import cadquery as cq

a = cq.Workplane("XY").box(1, 1, 1)
b = cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 0)).box(2, 2, 2)
c = cq.Workplane("XY").transformed(offset=cq.Vector(0, 5, 0)).box(1, 2, 3)
show_object(a.union(b).union(c))
