import cadquery as cq

result = cq.Workplane("XZ").moveTo(3, 1).circle(2).extrude(5)
