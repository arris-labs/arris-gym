import cadquery as cq

result = cq.Workplane("XY").transformed(offset=cq.Vector(0, 0.5, 0)).box(4, 1, 4)
show_object(result)
