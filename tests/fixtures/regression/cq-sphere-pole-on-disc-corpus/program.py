import cadquery as cq

result = (
    cq.Workplane("XZ")
    .sphere(11.27)
    .union(
        cq.Workplane("XZ")
        .transformed(offset=cq.Vector(0.0, 0.0, -54.09), rotate=cq.Vector(0, 0, 0))
        .circle(4.28)
        .extrude(42.82)
    )
)

show_object(result)
