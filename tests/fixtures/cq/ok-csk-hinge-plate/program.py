import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(79.42, 119.13, 3.97)
    .faces(">Y").workplane()
    .pushPoints([[-19.855, -29.782], [-19.855, 0.0], [-19.855, 29.782]])
    .cskHole(4.17, 8.34, 82.0)
)

# Export
show_object(result)
