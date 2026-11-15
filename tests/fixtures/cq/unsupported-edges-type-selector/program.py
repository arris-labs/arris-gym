import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges("%LINE")
show_object(result)
