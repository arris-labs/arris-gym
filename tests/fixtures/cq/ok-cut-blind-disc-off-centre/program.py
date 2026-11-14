import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(2, 1).circle(1).cutBlind(-1.5)
show_object(result)
