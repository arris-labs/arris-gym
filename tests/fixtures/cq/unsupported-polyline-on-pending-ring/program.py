import cadquery as cq

result = cq.Workplane("XY").circle(3).circle(1).polyline([(0, 0), (1, 0), (1, 1)])
show_object(result)
