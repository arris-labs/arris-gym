import cadquery as cq

result = cq.Workplane("XY").hole(1)
show_object(result)
