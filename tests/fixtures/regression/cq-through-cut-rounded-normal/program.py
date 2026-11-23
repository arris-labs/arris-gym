import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(0, 45, 0))
    .box(2, 2, 2)
    .workplane(offset=1e17)
    .circle(0.5)
    .cutThruAll()
)
