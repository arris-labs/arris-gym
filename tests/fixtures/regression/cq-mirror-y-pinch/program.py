import cadquery as cq

result = cq.Workplane("XY").moveTo(0, 0).lineTo(2, 0).lineTo(0, 2).lineTo(2, 4).lineTo(0, 4).mirrorY().extrude(4)
