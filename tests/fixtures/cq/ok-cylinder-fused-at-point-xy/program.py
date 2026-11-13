import cadquery as cq

result = cq.Workplane("XY").box(4, 4, 2).workplane(offset=1).moveTo(1, 0).cylinder(2, 0.5)
