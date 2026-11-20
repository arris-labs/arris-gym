import cadquery as cq

part = (
    cq.Workplane("YZ")
    .cylinder(4, 1)
    .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, -5, 0)).box(10, 10, 10))
)
result = part.faces(">Y").workplane().hole(0.4, depth=0.4)
