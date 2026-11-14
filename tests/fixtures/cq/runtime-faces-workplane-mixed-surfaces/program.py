import cadquery as cq

result = cq.Workplane("XY").cylinder(0.2, 0.1).faces(">X").workplane().circle(0.01).extrude(0.1)
show_object(result)
