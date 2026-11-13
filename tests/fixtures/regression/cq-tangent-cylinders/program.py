import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 0, 0), rotate=cq.Vector(0, 0, 0))
    .cylinder(1, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(-1, 0, 0), rotate=cq.Vector(0, 0, 0))
        .cylinder(1, 1)
    )
)

show_object(result)
