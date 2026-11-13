import cadquery as cq

result = cq.Workplane("XY").union(cq.Workplane("XY").cylinder(6, 2))
show_object(result)
