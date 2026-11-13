import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(3, 0)
    .circle(1)
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0), rotate=cq.Vector(0, 0, 0)).box(2, 2, 2))
)

show_object(result)
