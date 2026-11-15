import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 2).faces(">Z").workplane().hole(3).faces(">Z").edges().fillet(0.5)
show_object(result)
