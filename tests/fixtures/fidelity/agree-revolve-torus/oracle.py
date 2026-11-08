import cadquery as cq

result = cq.Workplane('XZ').center(3, 0).circle(1).revolve(360, (-3, 0, 0), (-3, 1, 0))
