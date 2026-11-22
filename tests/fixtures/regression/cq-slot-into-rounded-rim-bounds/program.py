import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(52.41)
    .extrude(1.57)
    .faces(">X").workplane()
    .circle(41.925)
    .cutThruAll()
    .edges(">Z or <Z")
    .fillet(0.42)
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(47.167, 0.0, 0.0), rotate=cq.Vector(0, 0, 0))
            .box(21.97, 2.5, 2.57)
    )
)

# Export
show_object(result)