import cadquery as cq

a = cq.Workplane("XY").box(2, 2, 2)
b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2)
bar = cq.Workplane("XY").transformed(offset=cq.Vector(2.5, 0, 0)).box(5, 1, 1)
show_object(a.union(b).union(bar))
