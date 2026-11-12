import cadquery as cq

result = cq.Workplane("XY").moveTo(3, 2).circle(1).revolve(180, (0, 0, 0), (0, 1, 0))
