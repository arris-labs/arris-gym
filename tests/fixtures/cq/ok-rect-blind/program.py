import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(1, -2).rect(4, 2).cutBlind(-1)
show_object(result)
