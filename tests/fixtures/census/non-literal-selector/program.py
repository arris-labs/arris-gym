import cadquery as cq

top = ">Z"
result = (
    cq.Workplane("XY")
    .box(4, 4, 4)
    .faces(top)
    .edges(selector="|Z")
    .fillet(0.5)
    .edges(cq.selectors.NearestToPointSelector((0, 0, 4)))
    .vertices(">X" + " and >Y")
    .faces(">Z or <Z")
)
