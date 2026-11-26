import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(6.71)
    .extrude(7.2, taper=28.504)
    .faces(">X").workplane()
    .circle(2.8)
    .extrude(4.0, taper=-12.544)
    .faces(">X").workplane()
    .circle(3.69)
    .extrude(6.7)
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(3.875, 0.0, 12.677), rotate=cq.Vector(0, 0, 0))
            .cylinder(9.845, 0.89)
    )
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(3.685, -1.197, 12.677), rotate=cq.Vector(0, 0, 0))
            .cylinder(9.845, 0.89)
    )
    .faces("<X").workplane()
    .hole(5.59)
)

# Export
show_object(result)