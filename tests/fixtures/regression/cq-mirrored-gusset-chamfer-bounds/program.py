import cadquery as cq

result = (
    cq.Workplane("YZ")
    .moveTo(0, 0)
    .lineTo(6, 0)
    .lineTo(6, 3)
    .lineTo(3, 2)
    .lineTo(3, 6)
    .lineTo(0, 6)
    .mirrorY()
    .extrude(8)
    .edges(">X")
    .chamfer(0.5)
)
