import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(26.5, 1.105)
    .edges(">Z or <Z")
    .chamfer(0.33)
    .faces(">Z").workplane()
    .hole(0.66, depth=0.792)
)

# Export
show_object(result)
