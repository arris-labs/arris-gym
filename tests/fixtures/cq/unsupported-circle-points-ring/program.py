import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().pushPoints([(2, 1), (-2, -1)]).circle(0.5).circle(0.25).extrude(1)
)
show_object(result)
