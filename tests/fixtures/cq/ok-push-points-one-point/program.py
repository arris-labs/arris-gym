import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces(">Z").workplane().pushPoints([(1, 1)]).hole(1)
)
show_object(result)
