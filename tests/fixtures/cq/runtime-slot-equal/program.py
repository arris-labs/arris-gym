import cadquery as cq

result = cq.Workplane("XY").slot2D(4, 4, 0).extrude(2)
show_object(result)
