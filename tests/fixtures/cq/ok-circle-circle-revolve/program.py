import cadquery as cq

result = cq.Workplane("XY").circle(3).circle(1).revolve(360, (5, 0, 0), (5, 1, 0))
show_object(result)
