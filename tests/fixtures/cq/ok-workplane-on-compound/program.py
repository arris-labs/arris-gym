import cadquery as cq

a = cq.Workplane("XY").box(2, 2, 2)
b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 2)).box(2, 2, 2)
result = a.union(b).workplane(offset=1).box(1, 1, 1)
show_object(result)
