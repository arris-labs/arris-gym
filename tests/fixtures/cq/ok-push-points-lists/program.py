import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces(">Z").workplane().pushPoints([[-1.0, -2.0], [1.0, 0.0], [0.5, 2.2]]).hole(1)
)
show_object(result)
