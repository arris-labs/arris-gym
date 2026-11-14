import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().rarray(4, 3, 2, 2).circle(1).cutBlind(-1)
show_object(result)
