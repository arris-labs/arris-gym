import cadquery as cq

result = cq.Workplane("XY").box(6, 6, 2).workplane(offset=1).polygon(6, 2).extrude(1)
