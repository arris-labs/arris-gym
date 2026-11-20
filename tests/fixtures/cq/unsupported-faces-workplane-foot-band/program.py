import cadquery as cq

part = (
    cq.Workplane("XZ")
    .polyline([(0, -100), (-100, -100), (-100, 100), (0, 100)])
    .close()
    .revolve(359, (0, 0, 0), (0, 1, 0))
)
wp = part.faces(">X").workplane()
show_object(part)
