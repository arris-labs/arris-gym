import cadquery as cq

outer = 10.0
result = (
    cq.Workplane("XY")
    .circle(outer)
    .circle(4.5)
    .extrude(2.0)
    .faces(">Z")
    .edges()
    .chamfer(0.3)
)
show_object(result)
