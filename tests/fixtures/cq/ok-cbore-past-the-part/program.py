import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(2, 1)]).cboreHole(1, 2, 5)
)
show_object(result)
