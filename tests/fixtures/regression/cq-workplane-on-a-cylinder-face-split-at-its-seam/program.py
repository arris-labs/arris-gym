import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(4, 5)
    .union(cq.Workplane("XY").transformed(offset=cq.Vector(0, -11.5, 0)).box(5, 17, 4))
    .faces(">Z")
    .faces(">Z")
    .workplane()
    .pushPoints([(1, -10)])
    .hole(1, depth=1)
)
show_object(result)
