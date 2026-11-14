import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(2, 1), (-2, -1)]).circle(0.5).extrude(1, both=True)
)
show_object(result)
