import cadquery as cq

profile = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
result = profile.revolve(360)
show_object(result)
