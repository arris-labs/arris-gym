import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(30, 45, 60))
    .box(2, 4, 6)
)
show_object(result)
