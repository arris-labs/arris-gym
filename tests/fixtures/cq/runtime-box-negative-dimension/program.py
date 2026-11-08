import cadquery as cq

result = cq.Workplane("XY").box(-1, 2, 3)
show_object(result)
