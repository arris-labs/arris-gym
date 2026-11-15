import cadquery as cq

result = cq.Workplane("XY").cylinder(4, 2).edges(">X")
show_object(result)
