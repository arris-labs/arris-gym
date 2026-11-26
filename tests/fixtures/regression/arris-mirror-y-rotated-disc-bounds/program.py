import cadquery as cq

result = cq.Workplane("XY", origin=(3, 4, 5)).transformed(rotate=cq.Vector(0, 0, 30)).moveTo(0, -2).threePointArc((2, 0), (0, 2)).mirrorY().extrude(4)
