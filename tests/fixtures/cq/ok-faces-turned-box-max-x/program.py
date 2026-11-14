import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(0, 0, 90))
    .box(4, 6, 8)
    .faces(">X").workplane().moveTo(0.5, 0.25).polygon(3, 1.5).extrude(2)
)
show_object(result)
