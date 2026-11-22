import cadquery as cq

result = cq.Workplane("XY").polarArray(3, 45, 90, 1).rect(4, 2).rect(2, 1).extrude(2)
show_object(result)
