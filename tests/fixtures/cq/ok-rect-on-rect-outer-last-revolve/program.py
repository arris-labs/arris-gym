import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).rect(2, 1).rect(6, 4).revolve(360, (-4, 0), (-4, 1))
show_object(result)
