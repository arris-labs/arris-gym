import cadquery as cq

result = cq.Workplane("XZ").cylinder(6, 2).faces("<Y").workplane().moveTo(0.5, 0.25).polygon(3, 1.5).extrude(2)
show_object(result)
