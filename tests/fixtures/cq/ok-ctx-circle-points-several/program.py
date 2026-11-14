import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(-1.0, -2.0), (1.0, 0.0), (0.5, 2.2)]).circle(0.5).extrude(1)
)
show_object(result)
