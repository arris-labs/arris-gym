import cadquery as cq

result = cq.Workplane("XY").pushPoints([(-3, 0), (3, 0)]).slot2D(6, 2, 0).extrude(2)
show_object(result)
