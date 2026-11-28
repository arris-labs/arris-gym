import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(19.05)
    .extrude(35.0)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(18.28, 0.0, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(9.14, 15.831, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-9.14, 15.831, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-18.28, 0.0, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-9.14, -15.831, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(9.14, -15.831, 0), rotate=cq.Vector(0, 0, 0))
            .circle(21.72)
            .extrude(35.0)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, -15.0), rotate=cq.Vector(0, 0, 0))
            .circle(12.0)
            .extrude(15.0)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, -16.0), rotate=cq.Vector(0, 0, 0))
            .circle(6.0)
            .extrude(52.0)
    )
)

# Export
show_object(result)