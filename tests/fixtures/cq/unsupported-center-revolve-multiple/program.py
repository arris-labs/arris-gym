import cadquery as cq

result = cq.Workplane("XY").circle(1).center(4,0).circle(1).revolve(360,(0,-3),(1,-3))
show_object(result)
