import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).lineTo(2, 0).lineTo(2, 3).lineTo(0, 3).mirrorY().extrude(4)
