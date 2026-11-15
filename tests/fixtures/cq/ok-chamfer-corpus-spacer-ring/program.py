import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(17.915)
    .extrude(0.43)
    .faces(">X").workplane()
    .hole(25.59)
    .edges(">Z or <Z")
    .chamfer(0.13)
)

# Export
show_object(result)
