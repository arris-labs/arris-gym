import cadquery as cq

result = cq.Workplane("XY").transformed(offset=cq.Vector(1, 0.5, 0)).box(4, 2, 2)
show_object(result)
