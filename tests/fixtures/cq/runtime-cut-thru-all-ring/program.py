import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(1, -1).circle(2).circle(1).cutThruAll()
show_object(result)
