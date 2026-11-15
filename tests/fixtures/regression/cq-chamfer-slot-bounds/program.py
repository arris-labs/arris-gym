import cadquery as cq

result = (
    cq.Workplane("XZ")
    .circle(21.19)
    .extrude(1.51)
    .edges(">Z or <Z")
    .chamfer(0.4)
    .cut(
        cq.Workplane("XZ")
            .transformed(offset=cq.Vector(18.163, 0.0, 0.0), rotate=cq.Vector(0, 0, 0))
            .box(13.11, 2.5, 2.51)
    )
)
show_object(result)
