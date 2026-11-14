import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().workplane(offset=-1).circle(1).cutBlind(2)
show_object(result)
