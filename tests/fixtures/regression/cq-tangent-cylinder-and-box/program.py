import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(4, 4, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(3, 0, 0), rotate=cq.Vector(0, 0, 0))
        .cylinder(2, 1)
    )
)

show_object(result)
