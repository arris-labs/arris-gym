import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(0, 45, 0))
    .box(6, 4, 2)
    .workplane(offset=1e17)
    .circle(0.5)
    .center(1.5, 0)
    .circle(0.5)
    .center(1, 0)
    .cutThruAll()
)
