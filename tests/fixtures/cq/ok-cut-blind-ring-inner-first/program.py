import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().circle(1).circle(2).cutBlind(-1)
show_object(result)
