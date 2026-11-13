import cadquery as cq

result = cq.Workplane("XY").box(1, 1, 1).union(cq.Workplane("XY").moveTo(5, 0).box(1, 1, 1)).polygon(6, 1).extrude(1)
show_object(result)
