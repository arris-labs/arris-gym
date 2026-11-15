import cadquery as cq

result = cq.Workplane("XY").chamfer(1)
show_object(result)
