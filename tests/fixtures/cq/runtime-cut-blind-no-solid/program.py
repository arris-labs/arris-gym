import cadquery as cq

result = cq.Workplane("XY").circle(1).cutBlind(-1)
show_object(result)
