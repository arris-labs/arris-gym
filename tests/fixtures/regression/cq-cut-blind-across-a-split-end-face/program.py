import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(0, 0), (6, 0), (10, 0), (10, 3), (0, 3)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .faces("<Y").workplane()
    .circle(7)
    .cutBlind(-1)
)

show_object(result)
