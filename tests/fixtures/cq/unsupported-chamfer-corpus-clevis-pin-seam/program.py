import cadquery as cq

result = (
    cq.Workplane("XZ")
    .cylinder(42.77, 5.94)
    .edges(">Z or <Z")
    .chamfer(1.19)
)

# Export
show_object(result)
