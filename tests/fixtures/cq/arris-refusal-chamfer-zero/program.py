import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges("|Z").chamfer(0)
show_object(result)
