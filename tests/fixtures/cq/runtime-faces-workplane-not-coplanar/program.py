import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(30, 0, 0))
    .polyline([(0, 0), (0.2, 0), (0, 0.15)])
    .close()
    .extrude(0.05)
    .faces(">X")
    .workplane()
    .circle(0.005)
    .extrude(0.05)
)
show_object(result)
