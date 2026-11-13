import cadquery as cq

result = cq.Workplane("XY").text("arris", 5, 1)
show_object(result)
