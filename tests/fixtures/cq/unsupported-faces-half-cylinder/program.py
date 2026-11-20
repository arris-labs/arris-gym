import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(4, 1)
    .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, -5, 0)).box(10, 10, 10))
    .faces(">Y")
    .workplane()
)
show_object(result)
