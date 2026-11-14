import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(10, 2, 1)
    .union(cq.Workplane("XY").transformed(offset=cq.Vector(-3, 0, 1)).box(2, 2, 1))
    .union(cq.Workplane("XY").transformed(offset=cq.Vector(4, 0, 1)).box(1, 2, 1))
    .faces(">Z")
    .workplane()
    .moveTo(-3, 0.25)
    .polygon(3, 1.5)
    .extrude(2)
)
show_object(result)
