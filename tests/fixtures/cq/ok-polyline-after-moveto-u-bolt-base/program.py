import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(0, 0, -2.405), rotate=cq.Vector(0, 0, 0))
    .box(121.25, 26.46, 4.81)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-42.59, 0.0, -9.11), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude(4.8, both=True)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(42.59, 0.0, -9.11), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude(4.8, both=True)
    )
)

# Export
show_object(result)
