import cadquery as cq

result = cq.Workplane("XY").cutThruAll()
show_object(result)
