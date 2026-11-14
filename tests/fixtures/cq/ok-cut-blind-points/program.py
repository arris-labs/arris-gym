import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(-3, -2), (3, 2)]).circle(0.5).cutBlind(-1)
show_object(result)
