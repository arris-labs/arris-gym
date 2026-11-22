import cadquery as cq

result = cq.Workplane("XY").pushPoints([(-3, -2), (2, 1)]).slot2D(6, 2, 90).extrude(2)
show_object(result)
