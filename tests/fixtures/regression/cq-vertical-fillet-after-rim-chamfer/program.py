import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(97.19, 66.88, 50.44)
    .faces(">Z")
    .chamfer(0.43)
    .edges("|Z")
    .fillet(1.71)
)
