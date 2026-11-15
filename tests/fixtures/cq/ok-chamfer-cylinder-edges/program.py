import cadquery as cq

result = cq.Workplane("XY").cylinder(4, 2).edges().chamfer(0.5)
show_object(result)
