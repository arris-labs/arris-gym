import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(4, 6, 8)
    .faces(">Z").workplane()
    .hole(1)
    .cut(cq.Workplane("XY").box(1, 1, 20))
)

show_object(result)
