import cadquery as cq

plate = (
    cq.Workplane("XY", origin=(0, 0, -10.075))
    .moveTo(49.933, -10.446)
    .lineTo(49.933, 10.446)
    .lineTo(10.437, 26.187)
    .threePointArc((0, 28.19), (-10.437, 26.187))
    .lineTo(-49.933, 10.446)
    .lineTo(-49.933, -10.446)
    .lineTo(-10.437, -26.187)
    .lineTo(10.437, -26.187)
    .close()
    .extrude(6.88)
)
result = cq.Workplane("XY").cylinder(19.15, 28.19).union(plate)
