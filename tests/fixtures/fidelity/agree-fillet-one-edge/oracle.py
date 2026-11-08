import cadquery as cq

result = cq.Workplane().box(6, 4, 3, centered=False).edges('|Y').edges('<X').edges('>Z').fillet(1)
