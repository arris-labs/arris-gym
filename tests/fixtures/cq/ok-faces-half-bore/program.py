import cadquery as cq

r = 2
h = 4
body = cq.Workplane("YZ").cylinder(h, 2 * r)
half = cq.Workplane("YZ").cylinder(2 * h, r).cut(
    cq.Workplane("XY", origin=(0, 0, -3 * r)).box(3 * h, 6 * r, 6 * r)
)
part = body.cut(half)
result = part.faces(">Z").workplane().moveTo(0, -2.6).hole(0.4, depth=0.4)
