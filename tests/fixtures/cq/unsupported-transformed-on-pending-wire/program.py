import cadquery as cq

result = cq.Workplane("XY").circle(1).transformed(offset=cq.Vector(0, 0, 1)).box(1, 1, 1)
show_object(result)
