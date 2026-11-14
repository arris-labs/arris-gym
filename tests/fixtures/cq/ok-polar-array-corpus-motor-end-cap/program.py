import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(25.15, 85.015)
    .faces(">Z").workplane()
    .hole(44.58)
    .faces(">Z").workplane()
    .polarArray(31.43, 0, 360, 6)
    .hole(7.96)
)

# Export
show_object(result)
