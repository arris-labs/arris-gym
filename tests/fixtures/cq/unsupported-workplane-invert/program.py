import cadquery as cq

result = cq.Workplane("XY").workplane(offset=2, invert=True).box(1, 1, 1)
show_object(result)
