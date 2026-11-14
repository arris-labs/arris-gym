import cadquery as cq

result = cq.Workplane("XY").cylinder(4, 1).faces(">X").workplane()
show_object(result)
