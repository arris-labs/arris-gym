import cadquery as cq

result = (
    cq.Workplane("XZ").circle(12).extrude(17.28)
    .faces(">Y").workplane()
    .hole(6.8)
    .faces(">Y").edges()
    .fillet(0.8)
    .faces(">Y").workplane()
    .pushPoints([(0.0, 3.4)])
    .rect(3.1, 1.86)
    .cutThruAll()
)
