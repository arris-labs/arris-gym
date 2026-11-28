import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(0, 0, 3.055), rotate=cq.Vector(0, 0, 0))
    .box(81.98, 77.79, 6.11)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 38.895, 0), rotate=cq.Vector(-30.6, 0, 0))
            .transformed(offset=cq.Vector(0, 0, 58.25), rotate=cq.Vector(0, 0, 0))
            .box(81.98, 6.11, 116.5)
    )
)

# Export
show_object(result)