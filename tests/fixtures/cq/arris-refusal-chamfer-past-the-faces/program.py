import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).edges("|Z").chamfer(4.5)
show_object(result)
