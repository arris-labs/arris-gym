import cadquery as cq

result = cq.Workplane("XY").pushPoints([(0, 0)]).slot2D(2, 4, 0).extrude(2)
show_object(result)
