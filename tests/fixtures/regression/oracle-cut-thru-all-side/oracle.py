import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">X").workplane().moveTo(1, -0.5).circle(1).cutThruAll()
show_object(result)
