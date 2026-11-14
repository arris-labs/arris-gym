import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().cutBlind(-1)
show_object(result)
