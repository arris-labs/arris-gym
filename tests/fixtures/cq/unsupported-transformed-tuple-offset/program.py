import cadquery as cq

result = cq.Workplane("XY").transformed(offset=(0, 0, 1)).box(1, 1, 1)
show_object(result)
