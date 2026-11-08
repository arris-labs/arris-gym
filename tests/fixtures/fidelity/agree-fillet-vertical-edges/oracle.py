import cadquery as cq

result = cq.Workplane().box(10, 10, 10, centered=False).edges('|Z').fillet(2)
