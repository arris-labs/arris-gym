import cadquery as cq

result = cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 1)).box(4, 2, 4)
show_object(result)
