import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges("|Z").fillet(0)
show_object(result)
