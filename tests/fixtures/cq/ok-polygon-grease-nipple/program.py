import cadquery as cq

result = (
    cq.Workplane("XZ")
    .moveTo(0.0, 0.0)
    .lineTo(4.3, 0.0)
    .lineTo(5.0, 0.7)
    .lineTo(5.0, 5.5)
    .lineTo(2.511, 5.5)
    .lineTo(2.511, 8.5)
    .lineTo(2.511, 12.997)
    .lineTo(3.78, 15.492)
    .lineTo(1.788, 16.0)
    .lineTo(0.0, 16.0)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .union(
        cq.Workplane("XY")
            .workplane(offset=5.5)
            .polygon(6, 12.702)
            .extrude(3.0)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, -1), rotate=cq.Vector(0, 0, 0))
            .circle(1.25)
            .extrude(18.0)
    )
)

show_object(result)
