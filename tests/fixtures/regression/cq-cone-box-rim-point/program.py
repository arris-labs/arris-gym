import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(2, 0)
    .lineTo(3, 2)
    .lineTo(0, 2)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .union(cq.Workplane("XY").transformed(offset=cq.Vector(3.5, 1.5, 0), rotate=cq.Vector(0, 0, 0)).box(1, 1, 1))
)

show_object(result)
