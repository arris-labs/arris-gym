import cadquery as cq

result = cq.Workplane("XY").moveTo(5e-08, 0).lineTo(2, 0).lineTo(2, 3).lineTo(5e-08, 3).mirrorY().extrude(4)
