import cadquery as cq

result = (cq.Workplane("XY").box(10, 2, 1).union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1)).union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1.00005)).box(1, 2, 1)).faces(">Z").workplane())
show_object(result)
