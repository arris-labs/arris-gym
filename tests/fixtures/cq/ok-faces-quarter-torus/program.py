import cadquery as cq

part = (
    cq.Workplane("XZ")
    .transformed(rotate=cq.Vector(0, -45, 0))
    .moveTo(5, 0)
    .circle(1)
    .revolve(90, (0, 0, 0), (0, 1, 0))
)
result = part.faces(">X").workplane(offset=-0.6).hole(0.4, depth=0.3)
