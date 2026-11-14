import cadquery as cq

result = cq.Workplane("XY").box(1, 1, 1).moveTo(5, 5).polyline([(0, 0), (3, 0), (0, 4)]).close().extrude(2)
show_object(result)
