import cadquery as cq

result = cq.Workplane("XY").cut(cq.Workplane("XY").cylinder(6, 2))
show_object(result)
