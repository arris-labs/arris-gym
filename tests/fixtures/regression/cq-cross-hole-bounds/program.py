import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(2)
    .extrude(2)
    .cut(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, 1), rotate=cq.Vector(90, 0, 0))
        .cylinder(6, 0.5)
    )
)

show_object(result)
