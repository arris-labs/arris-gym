import cadquery as cq

result = cq.Workplane("XY").edges(">Z")
show_object(result)
