import cadquery as cq

result = cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 1.5)).box(3, 3, 3)
show_object(result)
