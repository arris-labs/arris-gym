import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(20.0, 20.0, 10.0)
    .faces(">Z").workplane()
    .hole(4.0)
    .edges(">Z")
    .chamfer(0.5)
    .faces(">Z").workplane()
    .center(0.0, 1.25)
    .rect(1.0, 2.5)
    .cutThruAll()
)
