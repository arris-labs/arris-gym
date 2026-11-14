import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces(">Z").workplane().pushPoints([(20, 0)]).hole(1)
)
show_object(result)
