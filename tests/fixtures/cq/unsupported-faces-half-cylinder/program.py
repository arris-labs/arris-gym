import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(4, 1)
    .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, -5)).box(10, 10, 10))
    .faces(">Z")
    .workplane()
)
show_object(result)
