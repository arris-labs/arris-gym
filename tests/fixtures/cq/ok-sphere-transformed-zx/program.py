import cadquery as cq

result = (
    cq.Workplane("ZX")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(90, 0, 0))
    .sphere(1)
)
