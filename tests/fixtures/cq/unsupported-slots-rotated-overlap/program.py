import cadquery as cq

result = cq.Workplane("XY").polarArray(1, 0, 90, 2).slot2D(6, 2, 0).extrude(2)
show_object(result)
