import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(0, 0, 0))
    .box(2, 4, 6)
)
show_object(result)
