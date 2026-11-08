import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(1.0)
    .extrude(1.0)
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(1.0, 0.0, 0), rotate=cq.Vector(0, 0, 0))
        .circle(1.0)
        .extrude(1.0)
    )
    .union(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0.5, 0.8660254037844386, 0), rotate=cq.Vector(0, 0, 0))
        .circle(1.0)
        .extrude(1.0)
    )
)

show_object(result)
