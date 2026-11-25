import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(0, 0), (6, 0), (10, 2), (0, 2)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .faces(">Y")
    .workplane()
    .polarArray(10, 0, 360, 2)
    .circle(2)
    .cutBlind(-2)
)
