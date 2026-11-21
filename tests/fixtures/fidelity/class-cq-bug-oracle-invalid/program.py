import cadquery as cq

helix = cq.Wire.makeHelix(2.0, 10.0, 3.0)
result = cq.Workplane("XY").circle(0.5).sweep(cq.Workplane("XZ").add(helix))
