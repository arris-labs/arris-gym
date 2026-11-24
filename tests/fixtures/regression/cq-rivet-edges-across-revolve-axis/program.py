import cadquery as cq

result = (
    cq.Workplane("XZ")
    .moveTo(0, 6.25)
    .threePointArc((3.464, 4.625), (4, 3))
    .lineTo(2.5, 3)
    .lineTo(2.5, 0)
    .lineTo(0, 0)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .edges("<Y")
    .chamfer(0.5)
)
