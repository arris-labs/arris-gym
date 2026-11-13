import cadquery as cq

result = cq.Workplane("YZ").union(cq.Workplane("XY").box(2, 2, 2)).workplane(offset=1.25).box(1, 1, 1)
show_object(result)
