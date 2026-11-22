import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(1, 0).circle(3).rect(2, 1).cutBlind(-5)
show_object(result)
