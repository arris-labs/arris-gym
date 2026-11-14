import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(2, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, -1, 0), rotate=cq.Vector(0, 0, 0))
        .cylinder(1, 2)
    )
)

show_object(result)
