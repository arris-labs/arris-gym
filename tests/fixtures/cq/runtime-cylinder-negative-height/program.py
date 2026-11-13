import cadquery as cq

result = cq.Workplane("XY").cylinder(-2, 1)
show_object(result)
