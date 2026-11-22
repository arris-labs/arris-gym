import cadquery as cq

result = cq.Workplane("XY").circle(1).cutThruAll()
show_object(result)
