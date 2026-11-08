import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(90, 0, 0))
    .circle(1)
    .extrude(2)
)
show_object(result)
