import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(4, 4, 2)
    .workplane(offset=1)
    .moveTo(-1, 0)
    .threePointArc((0, 1), (1, 0))
    .close()
    .extrude(1)
)

show_object(result)
