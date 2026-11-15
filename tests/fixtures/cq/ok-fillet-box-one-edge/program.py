import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges(">Z").edges(">X").fillet(1)
show_object(result)
