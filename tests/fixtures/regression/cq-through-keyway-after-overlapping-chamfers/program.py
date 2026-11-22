import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(3.84)
    .extrude(8)
    .faces(">Z")
    .workplane()
    .hole(3.27)
    .faces(">Z")
    .edges()
    .chamfer(1.51)
    .faces(">Z")
    .workplane()
    .pushPoints([(0.0, 1.635)])
    .rect(1.55, 0.93)
    .cutThruAll()
)
