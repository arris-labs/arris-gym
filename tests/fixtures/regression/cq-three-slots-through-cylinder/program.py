import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(10, 4)
    .cut(cq.Workplane("XY").box(9, 1, 6))
    .cut(cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 60)).box(9, 1, 6))
    .cut(cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 120)).box(9, 1, 6))
)

show_object(result)
