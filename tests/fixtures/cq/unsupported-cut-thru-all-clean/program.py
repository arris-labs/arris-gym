import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(1, -2).circle(1).cutThruAll(clean=False)
show_object(result)
