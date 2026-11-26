import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(3.28)
    .extrude(5.4, taper=19.29)
    .faces(">Z")
    .workplane()
    .circle(1.39)
    .extrude(3.0, taper=-7.782)
    .faces(">Z")
    .workplane()
    .circle(1.8)
    .extrude(1.43)
    .cut(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(1.89, 0.0, 6.827), rotate=cq.Vector(0, 0, 0))
        .cylinder(5.407, 0.66)
    )
    .faces("<Z")
    .workplane()
    .hole(2.46)
)
