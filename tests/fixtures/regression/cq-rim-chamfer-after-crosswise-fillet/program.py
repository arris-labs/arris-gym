import cadquery as cq

result = cq.Workplane("XY").box(10, 20, 4).edges("|Y").fillet(0.5).faces(">Z").chamfer(1.0)
