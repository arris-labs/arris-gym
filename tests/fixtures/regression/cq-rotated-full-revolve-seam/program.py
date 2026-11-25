import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(0, 0, 180))
    .polyline([(0, -2), (2, -2), (2, 2), (0, 2)])
    .close()
    .revolve(360, (0, -2, 0), (0, 2, 0))
    .edges(">X")
    .chamfer(0.25)
)
