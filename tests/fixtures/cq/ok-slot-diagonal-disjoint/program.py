import cadquery as cq

result = cq.Workplane("XY").pushPoints([(0, 0), (-2, 2)]).slot2D(6, 2, 45).extrude(2)
show_object(result)
