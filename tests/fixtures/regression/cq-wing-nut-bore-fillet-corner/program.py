import cadquery as cq

hub = cq.Workplane("XY").circle(7).workplane(offset=8).circle(6.272).loft()
wing = (
    cq.Workplane("XZ")
    .moveTo(0, 0)
    .lineTo(7, 0)
    .lineTo(17.5, 10.5)
    .threePointArc((16.052, 14.373), (12.25, 16))
    .lineTo(5.5, 8)
    .lineTo(0, 8)
    .close()
    .extrude(0.583, both=True)
)
bore = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(0, 0, -1), rotate=cq.Vector(0, 0, 0))
    .circle(3.2)
    .extrude(18)
)
result = hub.union(wing).cut(bore).edges("|Y").fillet(0.443)
