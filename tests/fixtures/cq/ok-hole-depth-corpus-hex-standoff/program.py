import cadquery as cq

result = (
    cq.Workplane("XY")
    .polygon(6, 9.238)
    .extrude(9.26)
    .faces(">Z").workplane()
    .circle(2.315)
    .extrude(4.17)
    .faces("<Z").workplane()
    .hole(3.89, depth=6.02)
)

# Export
show_object(result)
