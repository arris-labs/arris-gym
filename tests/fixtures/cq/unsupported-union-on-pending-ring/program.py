import cadquery as cq

result = cq.Workplane("XY").circle(3).circle(1).union(cq.Workplane("XY").box(1, 1, 1))
show_object(result)
