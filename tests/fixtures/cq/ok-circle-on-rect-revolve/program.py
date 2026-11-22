import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).rect(6, 4).circle(1).revolve(360, (-4, 0), (-4, 1))
show_object(result)
