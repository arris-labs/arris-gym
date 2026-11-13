import cadquery as cq

result = cq.Workplane("XY").cylinder(2, 0)
show_object(result)
