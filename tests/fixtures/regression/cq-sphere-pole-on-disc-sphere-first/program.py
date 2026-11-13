import cadquery as cq

result = (
    cq.Workplane("XY")
    .sphere(2)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, -5), rotate=cq.Vector(0, 0, 0))
        .circle(1)
        .extrude(3)
    )
)

show_object(result)
