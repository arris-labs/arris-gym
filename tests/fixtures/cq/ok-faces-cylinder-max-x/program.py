import cadquery as cq

result = cq.Workplane("YZ").cylinder(6, 2).faces(">X").workplane().moveTo(0.5, 0.25).polygon(3, 1.5).extrude(2)
show_object(result)
