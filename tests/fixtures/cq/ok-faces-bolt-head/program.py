import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(2.0)
    .extrude(25.0)
    .faces(">Z").workplane()
    .polygon(6, 8.08)
    .extrude(2.8)
)

# Export
show_object(result)
