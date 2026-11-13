import cadquery as cq

result = cq.Workplane("XY").box(6, 6, 2).workplane(offset=1.5).moveTo(1, 0).sphere(1.5)
