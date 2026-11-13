import cadquery as cq

result = (
    cq.Workplane("XY")
    .lineTo(5, 0)
    .threePointArc((3, 4), (0, 5))
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
