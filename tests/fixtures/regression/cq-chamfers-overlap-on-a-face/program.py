import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(10.0)
    .extrude(8.0)
    .faces(">Z").workplane()
    .hole(12.0)
    .edges(">Z")
    .chamfer(2.5)
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0.0, 2.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .cylinder(30, 1)
    )
)
show_object(result)
