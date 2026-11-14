import cadquery as cq

result = (
    cq.Workplane("XZ").box(67.89, 37.56, 32.49).faces(">Z").workplane().pushPoints([(-8.122, 0.0), (0.001, 0.0), (8.124, 0.0)]).cboreHole(3.19, 5.54, 5.63)
)
show_object(result)
