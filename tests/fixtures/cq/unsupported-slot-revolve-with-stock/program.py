import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().slot2D(4, 2, 0).revolve(360, (-6, 0), (-6, 1))
show_object(result)
