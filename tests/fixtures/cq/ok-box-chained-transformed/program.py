import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 0, 0), rotate=cq.Vector(-30, 0, 0))
    .transformed(offset=cq.Vector(0, 0, 5), rotate=cq.Vector(0, 0, 90))
    .box(2, 4, 6)
)
show_object(result)
