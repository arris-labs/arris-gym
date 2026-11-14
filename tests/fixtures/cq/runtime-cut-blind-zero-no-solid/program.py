import cadquery as cq

result = cq.Workplane("XY").circle(1).cutBlind(0)
show_object(result)
