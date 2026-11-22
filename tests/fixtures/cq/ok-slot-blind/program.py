import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().slot2D(6, 2, 0).cutBlind(-2)
show_object(result)
