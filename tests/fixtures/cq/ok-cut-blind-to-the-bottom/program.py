import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().circle(1).cutBlind(-4)
show_object(result)
