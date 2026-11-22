import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(6.0)
    .extrude(2.0)
    .faces(">X").workplane()
    .circle(4.5)
    .cutThruAll()
    .edges(">Z or <Z")
    .fillet(0.2)
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(4.0, 0.0, 0.0), rotate=cq.Vector(0, 0, 0))
            .box(6.0, 1.6, 5.0)
    )
)

# Export
show_object(result)