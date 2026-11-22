import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().rarray(4, 3, 2, 2).rect(2, 1).cutThruAll()
show_object(result)
