import cadquery as cq

cut = (
    cq.Workplane("XY")
    .transformed(rotate=cq.Vector(0, 0.0055, 0))
    .transformed(offset=cq.Vector(0, 0, -5))
    .box(10, 10, 10)
)
part = cq.Workplane("XY").sphere(3).cut(cut)
result = part.faces(">Z").workplane().moveTo(1.75, 0).hole(1.2, depth=1.2)
