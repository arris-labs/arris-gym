import cadquery as cq

result = cq.Workplane("XY").pushPoints([(1, 2, 3)]).slot2D(6, 2, 0).extrude(2)
show_object(result)
