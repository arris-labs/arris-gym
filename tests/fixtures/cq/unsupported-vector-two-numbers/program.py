import cadquery as cq

result = cq.Workplane("XY").transformed(offset=cq.Vector(1, 2))
show_object(result)
