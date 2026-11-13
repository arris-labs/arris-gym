import cadquery as cq

result = (
    cq.Workplane("XZ")
    .threePointArc((5, 5), (10, 0))
    .lineTo(10, -2)
    .lineTo(0, -2)
    .close()
    .extrude(-2)
)

show_object(result)
