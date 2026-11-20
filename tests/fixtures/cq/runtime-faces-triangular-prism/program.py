import cadquery as cq

result = (cq.Workplane("XY").polyline([(0, 0), (4, 0), (0, 3)]).close().extrude(1).faces(">X").workplane())
show_object(result)
