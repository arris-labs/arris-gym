import cadquery as cq

result = (
    cq.Workplane("XZ")
    .transformed(offset=cq.Vector(0.0, 0.0, -80.105), rotate=cq.Vector(0, 0, 0))
    .cylinder(102.99, 10.3)
    .union(cq.Workplane("XZ").sphere(28.61))
)

show_object(result)
