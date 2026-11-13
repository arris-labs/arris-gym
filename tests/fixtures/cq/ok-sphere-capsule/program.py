import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(81.05, 16.02)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0.0, 40.525), rotate=cq.Vector(0, 0, 0))
            .sphere(16.02)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0.0, -40.525), rotate=cq.Vector(0, 0, 0))
            .sphere(16.02)
    )
    .union(
        cq.Workplane("XY")
            .cylinder(3.96, 19.22)
    )
)

show_object(result)
