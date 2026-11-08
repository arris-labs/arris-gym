import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(2, 0), (3, 0), (3, 4), (2, 4)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
