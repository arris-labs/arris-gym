import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(8)
    .extrude(4)
    .faces(">Z").workplane()
    .circle(1.5)
    .cutBlind(-2)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, 2), rotate=cq.Vector(0, 0, 0))
        .cylinder(4, 2.5)
    )
    .faces(">Z").workplane()
    .circle(2.2)
    .cutBlind(-2.5)
)

show_object(result)
