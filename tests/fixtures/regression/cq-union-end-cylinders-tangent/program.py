import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(30, 5, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(12, 0, 0), rotate=cq.Vector(0, 0, 0))
        .cylinder(1, 3)
    )
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(-12, 0, 0), rotate=cq.Vector(0, 0, 0))
        .cylinder(1, 3)
    )
)

show_object(result)
