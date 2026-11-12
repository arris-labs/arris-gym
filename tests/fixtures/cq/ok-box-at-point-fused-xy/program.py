import cadquery as cq

result = cq.Workplane("XY").box(4, 4, 2).moveTo(1, 0).box(1, 1, 4)
