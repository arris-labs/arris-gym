import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(84.0, 84.0, 42.0)
    .edges("<Z")
    .fillet(1.24)
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 1.1149999999999984), rotate=cq.Vector(0, 0, 0))
            .box(79.54, 79.54, 39.97)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, -32.17, 14.0), rotate=cq.Vector(0, 0, 0))
            .box(77.54, 15.2, 3.5)
    )
)

# Export
show_object(result)
