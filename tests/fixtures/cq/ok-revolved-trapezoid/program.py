import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(2, 0)
    .lineTo(3, 0)
    .lineTo(4, 3)
    .lineTo(3, 3)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
