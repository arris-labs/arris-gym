import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-4)
show_object(result)
