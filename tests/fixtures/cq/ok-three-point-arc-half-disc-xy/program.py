import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(-2, 0)
    .threePointArc((0, 2), (2, 0))
    .close()
    .extrude(3)
)

show_object(result)
