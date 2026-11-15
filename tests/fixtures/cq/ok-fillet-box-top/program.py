import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges(">Z").fillet(1)
show_object(result)
