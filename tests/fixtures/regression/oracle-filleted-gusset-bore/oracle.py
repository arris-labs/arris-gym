import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(0.0, 0.0)
    .lineTo(30.36, 0.0)
    .lineTo(30.36, 9.56)
    .lineTo(9.56, 15.77)
    .lineTo(9.56, 30.36)
    .lineTo(0.0, 30.36)
    .mirrorY()
    .extrude(18.79)
    .edges("<Z")
    .fillet(0.59)
    .faces("<Y")
    .workplane()
    .pushPoints([(15.18, 1.105)])
    .hole(4.86)
)
