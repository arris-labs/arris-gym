import cadquery as cq

frustum = cq.Workplane("XY").polyline([(0, 0), (2, 0), (1, 3), (0, 3)]).close()
result = frustum.revolve(360, (0, 0, 0), (0, 1, 0))
show_object(result)
