import cadquery as cq

part = (
    cq.Workplane("XZ")
    .polyline([(0, 0), (2, 0), (1, 4), (0, 4)])
    .close()
    .revolve(180, (0, 0, 0), (0, 1, 0))
)
result = part.faces(">Y").workplane().moveTo(0, 1.5).hole(0.4, depth=0.4)
