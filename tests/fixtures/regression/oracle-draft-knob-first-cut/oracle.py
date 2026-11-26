import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(8.75)
    .extrude(9.9, taper=27.438)
    .faces(">X").workplane()
    .circle(3.61)
    .extrude(5.5, taper=-12.308)
    .faces(">X").workplane()
    .circle(4.81)
    .extrude(8.65)
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(5.05, 0.0, 17.136), rotate=cq.Vector(0, 0, 0))
            .cylinder(13.228, 0.87)
    )
)
