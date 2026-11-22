import cadquery as cq

result = cq.Workplane("XY").moveTo(1, -2).circle(3).rect(2, 1).revolve(360, (-4, 0), (-4, 1))
show_object(result)
