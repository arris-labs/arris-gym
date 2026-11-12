import cadquery as cq

result = cq.Workplane("XY").moveTo(5, 0).circle(1).extrude(2).box(1, 1, 1)
