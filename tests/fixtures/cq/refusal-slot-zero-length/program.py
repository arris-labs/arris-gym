import cadquery as cq

result = cq.Workplane("XY").slot2D(0, 2, 0).extrude(2)
show_object(result)
