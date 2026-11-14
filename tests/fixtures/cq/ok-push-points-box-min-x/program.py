import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces("<X").workplane().pushPoints([(0.8, 1.2), (-0.8, -1.2)]).hole(1)
)
show_object(result)
