import cadquery as cq

result = (
    cq.Workplane("YZ")
    .transformed(offset=cq.Vector(3, -2, 5))
    .polyline([(1, 2), (4, 2), (1, 6)])
    .close()
    .extrude(7)
)
