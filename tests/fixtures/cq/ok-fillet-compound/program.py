import cadquery as cq

result = cq.Workplane("XY").box(2, 2, 2).union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2)).edges("|Z").fillet(0.5)
show_object(result)
