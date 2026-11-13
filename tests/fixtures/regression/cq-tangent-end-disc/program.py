import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(5, 0, 1.5), rotate=cq.Vector(0, 0, 0))
    .cylinder(3, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, 3), rotate=cq.Vector(0, 90, 0))
        .cylinder(12, 1)
    )
)

show_object(result)
