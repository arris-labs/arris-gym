import cadquery as cq

result = cq.Workplane("XY").moveTo(2, 0).circle(1).extrude(1)
