import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(21.0, 11.0, 7.5)
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-6.23, 0, 1.15), rotate=cq.Vector(0, 0, 0))
            .polygon(6, 2.0321)
            .extrude(2.8, both=True)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0, 1.15), rotate=cq.Vector(0, 0, 0))
            .polygon(6, 2.6094)
            .extrude(2.8, both=True)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(6.23, 0, 1.15), rotate=cq.Vector(0, 0, 0))
            .polygon(6, 3.1868)
            .extrude(2.8, both=True)
    )
)

# Export
show_object(result)
