import cadquery as cq

result = cq.Workplane("XY").rect(2, 1).center(3, 0).rect(2, 1).extrude(2)
show_object(result)
