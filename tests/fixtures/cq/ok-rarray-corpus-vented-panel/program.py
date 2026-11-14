import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(140.67, 94.15, 10.76)
    .faces(">Y").workplane()
    .rarray(54.35, 33.58, 3, 3)
    .hole(11.66)
)

# Export
show_object(result)
