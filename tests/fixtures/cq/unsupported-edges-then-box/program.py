import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges(">Z").box(1, 1, 1)
show_object(result)
