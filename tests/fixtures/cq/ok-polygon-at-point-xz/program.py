import cadquery as cq

result = cq.Workplane("XZ").moveTo(3, 1).polygon(6, 2).extrude(5)
