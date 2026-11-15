import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").fillet(1)
show_object(result)
