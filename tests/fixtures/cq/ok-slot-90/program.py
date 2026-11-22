import cadquery as cq

result = cq.Workplane("XY").slot2D(6, 2, 90).extrude(2)
show_object(result)
