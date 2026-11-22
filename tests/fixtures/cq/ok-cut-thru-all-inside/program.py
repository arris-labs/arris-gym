import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().workplane(offset=-1).moveTo(1, -2).circle(1).cutThruAll()
show_object(result)
