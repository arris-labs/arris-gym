import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(112.3, 151.08, 14.57)
    .edges("|Y")
    .fillet(1.31)
    .faces(">Y").workplane()
    .rarray(1, 60.66, 1, 3)
    .rect(70.67, 7.23)
    .cutThruAll()
    .faces(">Y").workplane()
    .pushPoints([(37.45, 56.84), (37.45, -56.84), (-37.45, 56.84), (-37.45, -56.84)])
    .hole(5.37)
    .faces(">Y")
    .chamfer(1.42)
)
