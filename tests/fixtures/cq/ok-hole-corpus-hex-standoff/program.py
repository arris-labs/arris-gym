import cadquery as cq

result = (
    cq.Workplane("XZ")
    .polygon(6, 6.351)
    .extrude(19.67)
    .faces(">Y").workplane()
    .hole(3.28)
)

# Export
show_object(result)
