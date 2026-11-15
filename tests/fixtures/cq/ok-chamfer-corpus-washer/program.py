import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(5.0, 30.0)
    .faces(">X").workplane()
    .hole(34.0)
    .edges(">Z or <Z")
    .chamfer(0.4)
)

# Export
show_object(result)
