import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(1.0, 5.0)
    .faces(">X").workplane()
    .hole(5.3)
    .edges(">X")
    .fillet(0.25)
)

# Export
show_object(result)
