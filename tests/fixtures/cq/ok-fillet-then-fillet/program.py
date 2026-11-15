import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges("|Z").fillet(2).faces(">Z").edges().fillet(0.5)
show_object(result)
