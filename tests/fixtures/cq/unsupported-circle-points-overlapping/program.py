import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(0, 0), (0.5, 0)]).circle(0.5).extrude(1)
)
show_object(result)
