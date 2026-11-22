import cadquery as cq

result = cq.Workplane("XY").moveTo(3, 0).slot2D(6, 2, 90).revolve(360, (0, 0), (0, 1))
show_object(result)
