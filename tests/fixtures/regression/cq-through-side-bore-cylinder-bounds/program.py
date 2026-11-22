import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(0, 0), (6, 0), (6, 12), (0, 12)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .transformed(offset=cq.Vector(0, 5, 0), rotate=cq.Vector(0, 0, 0))
    .circle(2)
    .cutThruAll()
)
