import cadquery as cq

result = (
    cq.Workplane("XY")
    .union(cq.Workplane("XY").cylinder(6, 2))
    .cut(cq.Workplane("XY").cylinder(8, 1))
)
show_object(result)
