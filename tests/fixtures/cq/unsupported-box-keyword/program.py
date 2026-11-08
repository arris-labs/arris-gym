import cadquery as cq

result = cq.Workplane("XY").box(1, 2, 3, centered=False)
show_object(result)
