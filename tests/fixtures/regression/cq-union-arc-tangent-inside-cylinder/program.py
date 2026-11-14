import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(2, 1)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, -1.25), rotate=cq.Vector(0, 0, 0))
        .moveTo(0.5, 0)
        .lineTo(0.5, 0.5)
        .threePointArc((0, 1), (-0.5, 0.5))
        .lineTo(-0.5, 0)
        .close()
        .extrude(1)
    )
)

show_object(result)
