import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(40, 40, 20)
    .union(
        cq.Workplane("XY")
            .cylinder(20.01, 5)
    )
    .faces(">Z").workplane()
    .hole(2)
)

# Export
show_object(result)
