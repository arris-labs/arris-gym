import cadquery as cq

result = cq.Workplane("XY", origin=(3, 4, 5)).transformed(rotate=cq.Vector(0, 0, 33)).moveTo(0, 0).threePointArc((2, 1), (0, 2)).lineTo(0, 3).mirrorY().extrude(4)
