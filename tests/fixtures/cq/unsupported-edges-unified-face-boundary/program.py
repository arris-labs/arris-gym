import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(4, 5)
    .cut(cq.Workplane("XY").box(6, 2, 20))
    .faces(">Y")
    .edges(">X")
)
