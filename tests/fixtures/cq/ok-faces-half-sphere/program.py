import cadquery as cq

part = cq.Workplane("XY").sphere(3).cut(cq.Workplane("XY", origin=(-5, 0, 0)).box(10, 10, 10))
result = part.faces(">X").workplane().hole(0.4, depth=0.4)
