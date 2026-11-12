import cadquery as cq

result = (
    cq.Workplane("XY", origin=(1, 1, 0))
    .polyline([(-1, -1), (5, -1), (5, 1), (-1, 1)])
    .close()
    .extrude(2)
    .workplane()
    .box(1, 1, 4)
)
