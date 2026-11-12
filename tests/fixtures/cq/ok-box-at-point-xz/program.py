import cadquery as cq

result = cq.Workplane("XZ").moveTo(3, 1).box(2, 4, 6)
