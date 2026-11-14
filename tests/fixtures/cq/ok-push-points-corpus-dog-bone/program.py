import cadquery as cq

result = (
    cq.Workplane("XZ")
    .moveTo(-43.5, 6.46)
    .lineTo(43.5, 6.46)
    .threePointArc((59.29, 0.0), (43.5, -6.46))
    .lineTo(-43.5, -6.46)
    .threePointArc((-59.29, 0.0), (-43.5, 6.46))
    .close()
    .extrude(3.68)
    .faces(">Y").workplane()
    .pushPoints([(-43.5, 0.0), (43.5, 0.0)])
    .hole(11.46)
)

# Export
show_object(result)
