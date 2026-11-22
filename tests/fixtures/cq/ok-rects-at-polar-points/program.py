import cadquery as cq

result = cq.Workplane("XY").polarArray(3, 0, 360, 4).rect(2, 1).extrude(2)
show_object(result)
