import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(2, 0)
    .lineTo(3, 0)
    .lineTo(3, 4)
    .lineTo(2, 4)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
