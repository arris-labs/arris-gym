import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(8, 0).circle(1).cutThruAll()
show_object(result)
