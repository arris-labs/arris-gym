import cadquery as cq

result = cq.Workplane("XY").sphere(3).faces(">Z").workplane()
