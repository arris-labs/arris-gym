import cadquery as cq

result = cq.Workplane("XY").rarray(8, 1, 2, 1).slot2D(6, 2, 0).extrude(2)
show_object(result)
