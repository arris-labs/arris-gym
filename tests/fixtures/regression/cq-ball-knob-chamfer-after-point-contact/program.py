import cadquery as cq

result = (
    cq.Workplane("XY")
    .sphere(20.14)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0.0, -56.4), rotate=cq.Vector(0, 0, 0))
            .cylinder(72.52, 7.25)
    )
    .faces("<Z")
    .edges()
    .chamfer(1.35)
)

# Export
show_object(result)
