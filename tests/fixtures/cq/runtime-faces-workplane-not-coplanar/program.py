import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(30, 0, 0))
    .polyline([(0, 0), (0.4, 0), (0, 0.3)])
    .close()
    .extrude(0.1)
    .faces(">X")
    .workplane()
    .circle(0.01)
    .extrude(0.1)
)
show_object(result)
