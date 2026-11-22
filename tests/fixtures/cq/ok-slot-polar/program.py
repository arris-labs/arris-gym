import cadquery as cq

result = cq.Workplane("XY").polarArray(4, 90, 180, 2).slot2D(6, 2, 30).extrude(2)
show_object(result)
