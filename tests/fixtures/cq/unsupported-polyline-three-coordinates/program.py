import cadquery as cq

profile = cq.Workplane("XY").polyline([(0, 0, 0), (1, 0, 0), (1, 1, 0)]).close()
result = profile.extrude(1)
show_object(result)
