import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(3, 2)]).hole(1).cboreHole(1, 2, 0.5)
)
show_object(result)
