import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(5.67)
    .extrude(6.3, taper=27.575)
    .faces(">Z")
    .workplane()
    .circle(2.38)
    .extrude(3.5, taper=-12.875)
    .faces(">Z")
    .workplane()
    .circle(3.18)
    .extrude(6.08)
    .cut(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(3.339, 0.0, 11.213), rotate=cq.Vector(0, 0, 0))
        .cylinder(8.734, 0.91)
    )
    .cut(
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(2.892, 1.669, 11.213), rotate=cq.Vector(0, 0, 0))
        .cylinder(8.734, 0.91)
    )
)
