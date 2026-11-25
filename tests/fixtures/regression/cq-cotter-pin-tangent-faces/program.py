import cadquery as cq

right = cq.Workplane("XY", origin=(1, 0, -0.5)).cylinder(1, 1)
left = cq.Workplane("XY", origin=(-1, 0, -0.5)).cylinder(1, 1)
head = cq.Workplane("XY").moveTo(1, 0).circle(1).revolve(180, (0, 0, 0), (0, -1, 0))
result = right.union(left).union(head)
