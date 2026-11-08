import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(2, 2, 2)
    .transformed(offset=cq.Vector(0, 0, 1.5))
    .box(2, 2, 2)
)
show_object(result)
