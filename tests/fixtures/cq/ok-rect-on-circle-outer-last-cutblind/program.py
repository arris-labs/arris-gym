import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(1, 0).circle(1).rect(6, 4).cutBlind(-5)
show_object(result)
