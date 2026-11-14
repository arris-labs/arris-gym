import cadquery as cq

result = cq.Workplane("XY").box(4, 6, 8).faces("<Z").workplane().moveTo(0.5, 0.25).polygon(3, 1.5).extrude(2)
show_object(result)
