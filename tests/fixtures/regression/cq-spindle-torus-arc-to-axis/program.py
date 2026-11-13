import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(8, 0)
    .threePointArc((6, 4), (0, 4))
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
