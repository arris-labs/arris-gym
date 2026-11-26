import cadquery as cq

result = (
    cq.Workplane("XZ")
    .transformed(rotate=cq.Vector(0, 0, 120))
    .transformed(rotate=cq.Vector(24, 0, 0))
    .polyline([(0, -3), (0, 3), (8, 0)])
    .close()
    .extrude(2)
)
