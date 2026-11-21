import cadquery as cq

result = cq.Workplane("XY").box(4, 4, 4).workplane(offset=2).rarray(3, 3, 2, 1).circle(0.5).extrude(2)
