import cadquery as cq

result = (
    cq.Workplane("YZ")
    .moveTo(-4, 3)
    .lineTo(4, 3)
    .threePointArc((13, 0), (4, -3))
    .lineTo(-4, -3)
    .threePointArc((-13, 0), (-4, 3))
    .close()
    .extrude(2)
)

show_object(result)
