import cadquery as cq

result = cq.Workplane("XY").fillet(1)
show_object(result)
