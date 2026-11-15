import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(14.4, 25.5)
    .faces(">Z").workplane()
    .circle(12.5)
    .extrude(29.4)
    .faces(">Z").workplane()
    .circle(7.4)
    .extrude(18.3)
    .faces(">Z").workplane()
    .circle(4.1)
    .extrude(13.6)
    .faces(">Z")
    .chamfer(0.73)
    .faces("<Z")
    .faces("<Z").workplane()
    .hole(3.23)
)

# Export
show_object(result)
