import cadquery as cq

result = cq.Workplane("YZ", origin=(3, 4, 5)).moveTo(0, -2).threePointArc((1, 0), (0, 2)).mirrorY().extrude(-3)
