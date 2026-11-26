import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(8.0)
    .workplane(offset=10.0)
    .circle(6.272)
    .loft(combine=True)
    .union(
        cq.Workplane("XZ")
        .moveTo(0.0, 0.0)
        .lineTo(-8.0, 0.0)
        .lineTo(-19.5, 11.5)
        .threePointArc((-18.881, 17.276), (-13.75, 20.0))
        .lineTo(-6.25, 10.0)
        .lineTo(0.0, 10.0)
        .close()
        .extrude(0.744, both=True)
    )
    .cut(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, -1), rotate=cq.Vector(0, 0, 0))
        .circle(4.2)
        .extrude(22.0)
    )
    .edges("|Y")
    .fillet(0.61)
)
