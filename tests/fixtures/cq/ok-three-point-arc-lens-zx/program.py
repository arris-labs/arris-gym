import cadquery as cq

result = (
    cq.Workplane("ZX")
    .moveTo(-4, 0)
    .threePointArc((0, 2), (4, 0))
    .threePointArc((0, -2), (-4, 0))
    .close()
    .extrude(-3)
)

show_object(result)
