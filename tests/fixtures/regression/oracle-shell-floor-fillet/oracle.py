import cadquery as cq

cup = cq.Workplane("XY").box(145.67, 77.02, 21.06).faces(">Z").shell(-2.2)
result = cup.faces("<Z").edges("<Z").fillet(1.86)
