import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().polarArray(3, 0, 360, 4).circle(0.5).extrude(1)
show_object(result)
