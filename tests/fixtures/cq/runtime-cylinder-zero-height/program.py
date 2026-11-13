import cadquery as cq

result = cq.Workplane("XY").cylinder(0, 1)
show_object(result)
