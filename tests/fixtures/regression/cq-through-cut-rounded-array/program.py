import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(0, 45, 0))
    .box(6, 4, 2)
    .workplane(offset=1e17)
    .center(0.5, -0.5)
    .pushPoints([(-1, 0), (1, 0)])
    .rect(1, 1)
    .cutThruAll()
)
